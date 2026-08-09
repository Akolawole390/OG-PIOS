import type { ReactNode } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex flex-1 flex-col gap-6 p-8">{children}</main>
    </div>
  );
}
