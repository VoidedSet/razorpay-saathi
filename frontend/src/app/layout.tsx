import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Razorpay Saathi — Agentic Store",
  description:
    "A multi-agent AI commerce assistant powered by LangGraph and Razorpay. " +
    "Featuring a Sales Agent, Billing Agent, and Promo Agent orchestrated by a Store Manager.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
