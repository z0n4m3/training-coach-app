export const metadata = {
  title: "Training Coach",
  description: "Plan → execution → response → decision",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pl">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#f6f7f9", color: "#15171a" }}>
        {children}
      </body>
    </html>
  );
}
