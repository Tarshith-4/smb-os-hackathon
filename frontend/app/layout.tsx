import type { Metadata } from "next";
import "./globals.css";
import "./agent.css";

export const metadata: Metadata = {
  title: "SMB OS — Business command center",
  description: "Your AI operations team, with you in control.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
