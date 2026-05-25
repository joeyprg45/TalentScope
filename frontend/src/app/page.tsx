"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function HomePage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: 0,
  });

  const status = health.isLoading
    ? "確認中…"
    : health.isError
      ? "未接続"
      : (health.data?.status ?? "未接続");

  const ok = !health.isLoading && !health.isError && health.data?.status === "ok";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">ダッシュボード</h1>
        <p className="text-muted-foreground">TalentScope — 業務 AI エージェント</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            API 接続状態
            <Badge variant={ok ? "default" : "destructive"}>{status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          FastAPI:{" "}
          <code className="font-mono text-foreground">
            {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}
          </code>
        </CardContent>
      </Card>
    </div>
  );
}
