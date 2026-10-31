import type { Metadata, Viewport } from "next";
import { LiveOperator } from "@/components/live-operator";
import { DepositSuccessPopup } from "@/components/deposit-success-popup";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { brand } from "@/lib/brand";

export const metadata: Metadata = {
  metadataBase: new URL(brand.siteUrl),
  title: { default: `${brand.name} — ${brand.tagline}`, template: `%s · ${brand.name}` },
  description: brand.description,
  alternates: { canonical: "/" },
  openGraph: { type: "website", siteName: brand.name, title: brand.name, description: brand.description, url: brand.siteUrl },
  twitter: { card: "summary_large_image", title: brand.name, description: brand.description },
};

export const viewport: Viewport = { themeColor: brand.colors.page, width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preload" as="image" href="/images/hero_model_blonde.webp" type="image/webp" />
      </head>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">
          Skip to content
        </a>
        <AuthProvider>
          <Header />
          <main id="main" className="min-h-[60vh]">{children}</main>
          <Footer />
          <LiveOperator />
          <DepositSuccessPopup />
        </AuthProvider>
      </body>
    </html>
  );
}
