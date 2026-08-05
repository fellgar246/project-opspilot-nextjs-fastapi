import type { Metadata } from "next";

import { AuthProvider } from "@/features/auth/AuthProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "OpsPilot AI",
  description: "Local incident response platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
