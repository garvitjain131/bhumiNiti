import type { AppProps } from "next/app";
import Head from "next/head";
import "maplibre-gl/dist/maplibre-gl.css";
import "@/styles/globals.css";
import { AppShell } from "@/components/layout/AppShell";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Head>
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <meta name="description" content="National platform for land-governance research and policy innovation (SIH26019)" />
          <title>Land Policy Intelligence Platform</title>
        </Head>
        <AppShell>
          <Component {...pageProps} />
        </AppShell>
      </AuthProvider>
    </ThemeProvider>
  );
}
