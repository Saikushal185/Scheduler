import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Interview Scheduling & Evaluation",
  description:
    "Automated interview scheduling with faculty availability, panel groups and configurable evaluation metrics.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
