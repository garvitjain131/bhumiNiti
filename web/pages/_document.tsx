import { Head, Html, Main, NextScript } from "next/document";

// Applies the saved theme and sidebar state before the first paint (no flash of the wrong layout).
const RESTORE_UI = `try{var d=document.documentElement,t=localStorage.getItem('lpip.theme'),s=localStorage.getItem('lpip.sidebar');
if(t==='dark'||t==='light')d.dataset.theme=t;if(s==='collapsed')d.dataset.sidebar='collapsed';}catch(e){}`;

export default function Document() {
  return (
    <Html lang="en" className="h-full antialiased">
      <Head>
        <link rel="icon" href="/favicon.ico" />
        <script dangerouslySetInnerHTML={{ __html: RESTORE_UI }} />
      </Head>
      <body className="min-h-full">
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
