import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/hooks/use-auth";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Whaply",
    template: "%s | Whaply",
  },
  description: "Intelligent WhatsApp automation with human/AI collision detection. Let AI handle conversations, step in when you need to — zero conflicts.",
  keywords: ["WhatsApp automation", "AI chatbot", "WhatsApp business", "customer support automation"],
  authors: [{ name: "Whaply" }],
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://whaply.co"),
  icons: {
    icon: [
      { url: "/logo.png", type: "image/png" },
    ],
    apple: [
      { url: "/logo.png", type: "image/png" },
    ],
    shortcut: "/logo.png",
  },
  openGraph: {
    type: "website",
    siteName: "Whaply",
    title: "Whaply — WhatsApp Automation with Collision Detection",
    description: "Intelligent WhatsApp automation with human/AI collision detection. Let AI handle conversations, step in when you need to — zero conflicts.",
    images: [
      {
        url: "/logo.png",
        width: 1092,
        height: 1092,
        alt: "Whaply Logo",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: "Whaply — WhatsApp Automation",
    description: "Intelligent WhatsApp automation with human/AI collision detection.",
    images: ["/logo.png"],
  },
  themeColor: "#16a34a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          {children}
          <Toaster position="top-right" />
        </AuthProvider>
      </body>
    </html>
  );
}
