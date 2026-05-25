"use client";

import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { Sidebar } from "./sidebar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden min-w-0">
        {children}
      </main>
      <ChatSidebar />
    </div>
  );
}
