export const INTERESTS: { id: string; label: string }[] = [
  { id: "ai", label: "AI/ML" },
  { id: "python", label: "Python" },
  { id: "web", label: "Web" },
  { id: "cybersecurity", label: "Cybersecurity" },
  { id: "data", label: "Data" },
  { id: "hackathons", label: "Hackathons" },
  { id: "design", label: "Design" },
  { id: "robotics", label: "Robotics" },
  { id: "startups", label: "Startups" },
  { id: "careers", label: "Careers" },
  { id: "cloud", label: "Cloud" },
  { id: "open-source", label: "Open source" },
  { id: "public-speaking", label: "Public speaking" },
  { id: "music", label: "Music" },
  { id: "sports", label: "Sports" },
  { id: "volunteering", label: "Volunteering" },
  { id: "photography", label: "Photography" },
  { id: "product", label: "Product" },
  { id: "iot", label: "IoT" },
  { id: "mobile", label: "Mobile apps" },
  { id: "gaming", label: "Gaming" },
  { id: "writing", label: "Writing" },
  { id: "quiz", label: "Quizzing" },
  { id: "art", label: "Art" },
];

export const interestLabel = (id: string) => INTERESTS.find((i) => i.id === id)?.label ?? id;

export const BUDGETS: { label: string; value: number | null }[] = [
  { label: "Free", value: 0 },
  { label: "₹100", value: 100 },
  { label: "₹200", value: 200 },
  { label: "₹500", value: 500 },
  { label: "Any", value: null },
];
