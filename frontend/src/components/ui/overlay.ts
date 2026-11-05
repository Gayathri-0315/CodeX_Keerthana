import { createContext, useContext } from "react";

/**
 * True inside sheets and popups that animate out. Shared-layout animations (a sliding highlight) inside
 * them keep the close animation from finishing, which leaves an invisible layer that blocks taps.
 */
export const InOverlay = createContext(false);
export const useInOverlay = () => useContext(InOverlay);
