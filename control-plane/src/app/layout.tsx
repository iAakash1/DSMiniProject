import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "OmniSignal Control Plane",
  description: "Operator console for the OmniSignal distributed execution layer.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" style={{ colorScheme: "light" }}>
      <body>
        <div className="shell">
          <Nav />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
