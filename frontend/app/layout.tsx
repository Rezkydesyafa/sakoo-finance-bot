import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sakoo Finance Bot Dashboard",
  description: "Dashboard for Sakoo Finance Bot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
