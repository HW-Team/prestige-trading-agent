import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DCTS | วางระบบการเทรดให้เป็นกิจวัตร",
  description:
    "DCTS หลักสูตรการศึกษาด้านการเทรดที่เน้น Checklist การบันทึก และการบริหารความเสี่ยง",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    type: "website",
    locale: "th_TH",
    title: "DCTS | วางระบบการเทรดให้เป็นกิจวัตร",
    description:
      "หลักสูตรการศึกษาด้านการเทรดที่เน้น Checklist การบันทึก และการบริหารความเสี่ยง",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}
