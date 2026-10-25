import { AnimatePresence, m } from "motion/react";
import { ArrowLeft, Camera, CameraOff } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { CountUp } from "../../components/ui/CountUp";
import { ApiError } from "../../lib/api";
import { useAnalytics, useCheckin, type CheckinResult } from "../../lib/attendance";
import { formatTime } from "../../lib/format";
import { haptic, spring } from "../../lib/motion";
import { useOrgEvent } from "../../lib/organizer";

type Flash = { tone: "success" | "warning" | "danger"; text: string } | null;
const SCAN_COOLDOWN_MS = 2500;

export default function Checkin() {
  const { id = "" } = useParams();
  const event = useOrgEvent(id);
  const analytics = useAnalytics(id);
  const checkin = useCheckin(id);
  const [code, setCode] = useState("");
  const [flash, setFlash] = useState<Flash>(null);
  const [count, setCount] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const lastScan = useRef<{ token: string; at: number }>({ token: "", at: 0 });
  const flashTimer = useRef(0);

  const show = (f: Flash) => {
    setFlash(f);
    window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => setFlash(null), 1800);
  };

  const submit = (token: string) => {
    checkin.mutate(token, {
      onSuccess: (r: CheckinResult) => {
        setCount(r.count);
        if (r.status === "already") show({ tone: "warning", text: `${r.name} already checked in at ${formatTime(r.checked_in_at)}` });
        else {
          haptic(15);
          show({ tone: "success", text: `${r.name} checked in` });
        }
      },
      onError: (e) => show({ tone: "danger", text: e instanceof ApiError ? e.message : "Couldn't check in. Try again." }),
    });
  };

  const onManual = (e: FormEvent) => {
    e.preventDefault();
    if (code.trim()) submit(code.trim());
    setCode("");
  };

  // Camera scanning, loaded only when asked for.
  useEffect(() => {
    if (!scanning) return;
    let stopped = false;
    let scanner: { stop: () => Promise<void>; clear: () => void } | null = null;
    import("html5-qrcode").then(({ Html5Qrcode }) => {
      if (stopped) return;
      const s = new Html5Qrcode("qr-reader", { verbose: false });
      scanner = s;
      s.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (text) => {
          const now = Date.now();
          if (text === lastScan.current.token && now - lastScan.current.at < SCAN_COOLDOWN_MS) return;
          lastScan.current = { token: text, at: now };
          submit(text);
        },
        () => {},
      ).catch(() => {
        setCameraError("Couldn't open the camera. Allow camera access, or type the code instead.");
        setScanning(false);
      });
    });
    return () => {
      stopped = true;
      scanner?.stop().then(() => scanner?.clear()).catch(() => {});
    };
  }, [scanning]); // `submit` reads fresh state through the mutation, so only scanning restarts the camera

  const shownCount = count ?? analytics.data?.actual ?? 0;
  const total = analytics.data?.registered;

  return (
    <div className="mx-auto max-w-lg pb-16">
      <Link to={`/organizer/event/${id}`} className="pressable -ml-2 mb-3 inline-flex min-h-11 items-center gap-1 rounded-full px-2 callout font-medium text-accent">
        <ArrowLeft className="size-5" aria-hidden /> Event
      </Link>
      <h1 className="title-1">Check-in</h1>
      <p className="callout mt-1 text-text-2">{event.data?.form.title}</p>

      <div className="card mt-6 p-6 text-center" aria-live="polite">
        <p className="text-[56px] font-semibold leading-none tracking-tight tnum"><CountUp value={shownCount} /></p>
        <p className="callout mt-1 text-text-2 tnum">checked in{total != null ? ` of ${total}` : ""}</p>
      </div>

      <div className="card mt-4 overflow-hidden">
        {scanning ? (
          <div id="qr-reader" className="aspect-square w-full bg-black" />
        ) : (
          <div className="grid aspect-[4/3] place-items-center bg-surface-2 p-6 text-center">
            <div>
              <Camera className="mx-auto size-10 text-text-2" aria-hidden />
              <p className="callout mt-2 text-text-2">{cameraError ?? "Scan the QR on each attendee's pass."}</p>
            </div>
          </div>
        )}
        <div className="p-4">
          <Button full size="lg" variant={scanning ? "secondary" : "primary"} onClick={() => { setCameraError(null); setScanning((s) => !s); }}>
            {scanning ? <><CameraOff className="size-5" aria-hidden /> Stop camera</> : <><Camera className="size-5" aria-hidden /> Scan QR</>}
          </Button>
        </div>
      </div>

      <form onSubmit={onManual} className="card mt-4 flex items-end gap-3 p-4">
        <div className="flex-1">
          <label htmlFor="code" className="footnote mb-1.5 block font-medium text-text-2">Or type the code on their pass</label>
          <input
            id="code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            maxLength={36}
            autoComplete="off"
            placeholder="A1B2C3"
            className="h-12 w-full rounded-[14px] bg-surface-2 px-4 font-mono text-[17px] tracking-[0.2em] outline-none shadow-[inset_0_0_0_1px_var(--line)] focus:shadow-[inset_0_0_0_2px_var(--accent)]"
          />
        </div>
        <Button type="submit" size="lg" loading={checkin.isPending} disabled={code.trim().length < 6}>Check in</Button>
      </form>

      <AnimatePresence>
        {flash && (
          <m.div
            key={flash.text}
            className={`pointer-events-none fixed inset-0 z-[55] grid place-items-center ${flash.tone === "success" ? "bg-success/25" : flash.tone === "warning" ? "bg-warning/25" : "bg-danger/25"}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            role="status"
          >
            <m.p
              initial={{ scale: 0.8, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              transition={spring}
              className="glass mx-6 rounded-[22px] px-6 py-5 text-center title-3 shadow-card"
            >
              {flash.text}
            </m.p>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
