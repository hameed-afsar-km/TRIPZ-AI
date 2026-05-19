import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TRIPZ.AI - Multi-Agent AI Travel Planner",
  description: "Collaborate with dedicated AI agents to design your custom itinerary",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <link href="https://fonts.cdnfonts.com/css/kenyan-coffee" rel="stylesheet" />
      </head>
      <body className="min-h-full flex flex-col bg-[#09090b] text-[#f4f4f5]">{children}</body>
    </html>
  );
}
