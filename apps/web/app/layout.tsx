import type { Metadata } from "next";

import { AuthProvider } from "@/features/auth/AuthProvider";
import { QueryProvider } from "@/features/incidents/QueryProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "OpsPilot AI",
  description: "Local incident response platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <QueryProvider>{children}</QueryProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
