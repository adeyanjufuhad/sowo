import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const bricolage = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "Sowo: dey sell while you sleep",
    template: "%s · Sowo",
  },
  description:
    "An AI sales assistant for Nigerian vendors on WhatsApp. Sowo answers buyers instantly, haggles down to your floor price, sends a Paystack link and tells you when to pack. Built on the open-weight Qwen3 model.",
};

export const viewport: Viewport = {
  themeColor: "#f5f1ea",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en-NG"
      className={`${geist.variable} ${geistMono.variable} ${bricolage.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <noscript>
          <style>{`[data-reveal]{opacity:1!important;transform:none!important;filter:none!important}`}</style>
        </noscript>
        {children}
      </body>
    </html>
  );
}
