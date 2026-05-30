"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Plus, Save, RotateCcw, Trash2, Check, X, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { AbsoluteConstraint, ExtractionResult, PromptNode } from "@/lib/types";

// ─── プロンプトツリー ─────────────────────────────────────────────────────────

function flattenTree(nodes: PromptNode[]): PromptNode[] {
  const result: PromptNode[] = [];
  for (const node of nodes) {
    result.push(node);
    if (node.children.length > 0) result.push(...flattenTree(node.children));
  }
  return result;
}

function PromptTree({
  nodes, selectedId, onSelect, expanded, onToggle, depth = 0,
}: {
  nodes: PromptNode[];
  selectedId: string | null;
  onSelect: (node: PromptNode) => void;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  depth?: number;
}) {
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) => (
        <li key={node.id}>
          <div
            className={`flex items-center gap-1 rounded px-2 py-1.5 cursor-pointer text-sm transition-colors ${
              selectedId === node.id ? "bg-primary text-primary-foreground" : "hover:bg-muted"
            }`}
            style={{ paddingLeft: `${8 + depth * 16}px` }}
            onClick={() => {
              if (node.children.length > 0) onToggle(node.id);
              onSelect(node);
            }}
          >
            {node.children.length > 0 ? (
              expanded.has(node.id) ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />
            ) : (
              <span className="w-3 shrink-0" />
            )}
            <span className="truncate">{node.name}</span>
            {!node.is_selectable && <span className="ml-auto text-[10px] opacity-50">グループ</span>}
          </div>
          {node.children.length > 0 && expanded.has(node.id) && (
            <PromptTree nodes={node.children} selectedId={selectedId} onSelect={onSelect} expanded={expanded} onToggle={onToggle} depth={depth + 1} />
          )}
        </li>
      ))}
    </ul>
  );
}

// ─── メインページ ─────────────────────────────────────────────────────────────

type Tab = "prompts" | "memory";
type ConstraintFilter = "all" | "pending" | "active" | "dismissed";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("prompts");

  // ── プロンプトタブ state ──
  const [tree, setTree] = useState<PromptNode[]>([]);
  const [allNodes, setAllNodes] = useState<PromptNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<PromptNode | null>(null);
  const [editedLayer, setEditedLayer] = useState("");
  const [originalLayer, setOriginalLayer] = useState("");
  const [editedTrigger, setEditedTrigger] = useState("");
  const [originalTrigger, setOriginalTrigger] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["assignment"]));
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newParent, setNewParent] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [adding, setAdding] = useState(false);

  // ── 記憶タブ state ──
  const [unprocessedCount, setUnprocessedCount] = useState<number | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractResult, setExtractResult] = useState<ExtractionResult | null>(null);
  const [constraints, setConstraints] = useState<AbsoluteConstraint[]>([]);
  const [constraintFilter, setConstraintFilter] = useState<ConstraintFilter>("all");
  const [newConstraintText, setNewConstraintText] = useState("");
  const [addingConstraint, setAddingConstraint] = useState(false);
  const [qualitativeText, setQualitativeText] = useState("");
  const [originalQualitative, setOriginalQualitative] = useState("");
  const [savingQualitative, setSavingQualitative] = useState(false);
  const [qualitativeSaveMsg, setQualitativeSaveMsg] = useState("");
  const [memoryLoading, setMemoryLoading] = useState(false);

  // ── プロンプト初期ロード ──
  useEffect(() => {
    api.prompts().then((data) => {
      setTree(data);
      setAllNodes(flattenTree(data));
    });
  }, []);

  // ── 記憶タブ切替時にデータ取得 ──
  useEffect(() => {
    if (activeTab !== "memory") return;
    setMemoryLoading(true);
    Promise.all([
      api.memory.getUnprocessedCount(),
      api.memory.listConstraints(),
      api.memory.getQualitative(),
    ]).then(([countRes, constraintRes, qualRes]) => {
      setUnprocessedCount(countRes.count);
      setConstraints(constraintRes);
      setQualitativeText(qualRes.content);
      setOriginalQualitative(qualRes.content);
    }).finally(() => setMemoryLoading(false));
  }, [activeTab]);

  // ── プロンプトタブ handlers ──
  const handleSelect = (node: PromptNode) => {
    setSelectedNode(node);
    setEditedLayer(node.ceo_layer);
    setOriginalLayer(node.ceo_layer);
    setEditedTrigger(node.trigger_conditions);
    setOriginalTrigger(node.trigger_conditions);
    setSaveMsg("");
  };

  const handleToggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!selectedNode) return;
    setSaving(true);
    try {
      await api.updatePrompt(selectedNode.id, { ceo_layer: editedLayer, trigger_conditions: editedTrigger });
      setOriginalLayer(editedLayer);
      setOriginalTrigger(editedTrigger);
      setSaveMsg("保存しました");
      setAllNodes((prev) => prev.map((n) => n.id === selectedNode.id ? { ...n, ceo_layer: editedLayer, trigger_conditions: editedTrigger } : n));
      setSelectedNode({ ...selectedNode, ceo_layer: editedLayer, trigger_conditions: editedTrigger });
      setTimeout(() => setSaveMsg(""), 2000);
    } catch {
      setSaveMsg("保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setEditedLayer(originalLayer);
    setEditedTrigger(originalTrigger);
    setSaveMsg("");
  };

  const handleAdd = async () => {
    if (!newId || !newName) return;
    setAdding(true);
    try {
      await api.createPrompt({ id: newId, parent_id: newParent || null, name: newName, description: newDesc, ceo_layer: "", is_selectable: true });
      const data = await api.prompts();
      setTree(data);
      setAllNodes(flattenTree(data));
      setShowAddForm(false);
      setNewId(""); setNewName(""); setNewParent(""); setNewDesc("");
    } catch {
      // ignore
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (node: PromptNode) => {
    if (node.is_system) return;
    if (!confirm(`「${node.name}」を削除しますか？`)) return;
    await api.deletePrompt(node.id);
    const data = await api.prompts();
    setTree(data);
    setAllNodes(flattenTree(data));
    if (selectedNode?.id === node.id) { setSelectedNode(null); setEditedLayer(""); }
  };

  // ── 記憶タブ handlers ──
  const handleExtract = async () => {
    setExtracting(true);
    setExtractResult(null);
    try {
      const result = await api.memory.extractMemory();
      setExtractResult(result);
      // 一覧を更新
      const [countRes, constraintRes] = await Promise.all([
        api.memory.getUnprocessedCount(),
        api.memory.listConstraints(),
      ]);
      setUnprocessedCount(countRes.count);
      setConstraints(constraintRes);
    } catch {
      // ignore
    } finally {
      setExtracting(false);
    }
  };

  const handleConstraintStatus = async (id: string, status: "active" | "dismissed") => {
    try {
      await api.memory.updateConstraintStatus(id, status);
      setConstraints((prev) => prev.map((c) => c.id === id ? { ...c, status } : c));
    } catch {
      // ignore
    }
  };

  const handleConstraintDelete = async (id: string) => {
    try {
      await api.memory.deleteConstraint(id);
      setConstraints((prev) => prev.filter((c) => c.id !== id));
    } catch {
      // ignore
    }
  };

  const handleAddConstraint = async () => {
    if (!newConstraintText.trim()) return;
    setAddingConstraint(true);
    try {
      const created = await api.memory.createConstraint(newConstraintText.trim());
      setConstraints((prev) => [...prev, created]);
      setNewConstraintText("");
    } catch {
      // ignore
    } finally {
      setAddingConstraint(false);
    }
  };

  const handleSaveQualitative = async () => {
    setSavingQualitative(true);
    try {
      await api.memory.updateQualitative(qualitativeText);
      setOriginalQualitative(qualitativeText);
      setQualitativeSaveMsg("保存しました");
      setTimeout(() => setQualitativeSaveMsg(""), 2000);
    } catch {
      setQualitativeSaveMsg("保存に失敗しました");
    } finally {
      setSavingQualitative(false);
    }
  };

  const isDirty = editedLayer !== originalLayer || editedTrigger !== originalTrigger;
  const isQualitativeDirty = qualitativeText !== originalQualitative;
  const selectableNodes = allNodes.filter((n) => n.is_selectable);
  const pendingCount = constraints.filter((c) => c.status === "pending").length;

  const filteredConstraints = constraints.filter((c) => {
    if (constraintFilter === "all") return true;
    return c.status === constraintFilter;
  });

  const statusLabel: Record<AbsoluteConstraint["status"], string> = {
    pending: "⏳ 承認待ち",
    active: "✅ 有効",
    dismissed: "❌ 却下",
  };

  return (
    <div className="flex h-full flex-col">
      {/* ページヘッダー */}
      <div className="border-b px-6 py-4">
        <h1 className="text-xl font-bold">AI設定</h1>
        <p className="text-sm text-muted-foreground mt-1">
          エージェントの動作設定とCEOの判断基準を管理します。
        </p>
      </div>

      {/* タブバー */}
      <div className="flex border-b px-6 gap-1">
        {([["prompts", "プロンプト設定"], ["memory", "記憶・制約"]] as [Tab, string][]).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
            {tab === "memory" && pendingCount > 0 && (
              <span className="ml-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ─── プロンプト設定タブ ───────────────────────────────────────────────── */}
      {activeTab === "prompts" && (
        <div className="flex flex-1 overflow-hidden">
          <aside className="w-56 shrink-0 border-r overflow-y-auto p-3">
            <PromptTree nodes={tree} selectedId={selectedNode?.id ?? null} onSelect={handleSelect} expanded={expanded} onToggle={handleToggle} />
            <div className="mt-3 border-t pt-3">
              <button onClick={() => setShowAddForm(!showAddForm)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <Plus className="h-3.5 w-3.5" />
                モードを追加
              </button>
              {showAddForm && (
                <div className="mt-2 space-y-2 text-xs">
                  <input className="w-full rounded border px-2 py-1 text-xs" placeholder="ID（例: custom/my-mode）" value={newId} onChange={(e) => setNewId(e.target.value)} />
                  <input className="w-full rounded border px-2 py-1 text-xs" placeholder="表示名" value={newName} onChange={(e) => setNewName(e.target.value)} />
                  <select className="w-full rounded border px-2 py-1 text-xs bg-background" value={newParent} onChange={(e) => setNewParent(e.target.value)}>
                    <option value="">親なし（ルート）</option>
                    {allNodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                  </select>
                  <input className="w-full rounded border px-2 py-1 text-xs" placeholder="説明（任意）" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
                  <button onClick={handleAdd} disabled={adding || !newId || !newName} className="w-full rounded bg-primary text-primary-foreground py-1 text-xs disabled:opacity-50">
                    {adding ? "作成中..." : "作成"}
                  </button>
                </div>
              )}
            </div>
          </aside>

          <main className="flex-1 overflow-y-auto p-6">
            {selectedNode ? (
              <div className="max-w-2xl space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedNode.name}</h2>
                    {selectedNode.description && <p className="text-sm text-muted-foreground mt-0.5">{selectedNode.description}</p>}
                  </div>
                  {!selectedNode.is_system && (
                    <button onClick={() => handleDelete(selectedNode)} className="text-destructive hover:opacity-70 transition-opacity" title="削除">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div>
                  <label className="text-sm font-medium mb-1 block">発火条件</label>
                  <p className="text-xs text-muted-foreground mb-1">このモードが自動判別される場面を記述します。エージェントが会話の意図を分類する際に参照されます。</p>
                  <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary" rows={4} value={editedTrigger} onChange={(e) => setEditedTrigger(e.target.value)} placeholder="例: アサイン提案・チーム編成を実行してほしい明確なリクエスト。" />
                </div>

                <div className="rounded-md border bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
                  判断基準はアサイン・評価時の<strong>優先順位・価値観</strong>を記述する欄です。ツールの動作には影響しません。
                </div>

                <div>
                  <label className="text-sm font-medium mb-1 block">判断基準</label>
                  <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary" rows={10} value={editedLayer} onChange={(e) => setEditedLayer(e.target.value)} placeholder="例: スキル適合度を最優先にすること。GitHubの実装履歴がある候補は必ず確認する。" />
                </div>

                <div className="flex items-center gap-3">
                  <button onClick={handleSave} disabled={saving || !isDirty} className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity">
                    <Save className="h-3.5 w-3.5" />
                    {saving ? "保存中..." : "保存"}
                  </button>
                  <button onClick={handleReset} disabled={!isDirty} className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50 hover:bg-muted transition-colors">
                    <RotateCcw className="h-3.5 w-3.5" />
                    リセット
                  </button>
                  {saveMsg && <span className={`text-sm ${saveMsg.includes("失敗") ? "text-destructive" : "text-green-600"}`}>{saveMsg}</span>}
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                左のメニューからモードを選択してください
              </div>
            )}
          </main>
        </div>
      )}

      {/* ─── 記憶・制約タブ ──────────────────────────────────────────────────── */}
      {activeTab === "memory" && (
        <div className="flex-1 overflow-y-auto p-6">
          {memoryLoading ? (
            <p className="text-sm text-muted-foreground">読み込み中...</p>
          ) : (
            <div className="max-w-2xl space-y-8">

              {/* 学習セクション */}
              <section>
                <h2 className="text-base font-semibold mb-3">過去の会話から学習する</h2>
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground">未処理の会話:</span>
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        (unprocessedCount ?? 0) > 0 ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300" : "bg-muted text-muted-foreground"
                      }`}>
                        {unprocessedCount ?? "—"} 件
                      </span>
                    </div>
                    <button
                      onClick={handleExtract}
                      disabled={extracting || unprocessedCount === 0}
                      className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${extracting ? "animate-spin" : ""}`} />
                      {extracting ? "学習中..." : "学習を実行"}
                    </button>
                  </div>
                  {extractResult && (
                    <div className="rounded-md bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 px-3 py-2 text-xs text-green-800 dark:text-green-300">
                      ✅ {extractResult.processed} 件処理 / {extractResult.constraints_found} 件の条件を発見
                      {extractResult.qualitative_updated && " / 定性方針を更新"}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    過去のチャットからCEOの判断基準・禁止事項を自動抽出し、下の絶対条件リストに追加します。
                  </p>
                </div>
              </section>

              {/* 絶対条件 */}
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-base font-semibold">
                    絶対条件
                    {pendingCount > 0 && (
                      <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[11px] font-bold text-white">
                        {pendingCount} 件承認待ち
                      </span>
                    )}
                  </h2>
                  <div className="flex items-center gap-1">
                    {(["all", "pending", "active", "dismissed"] as ConstraintFilter[]).map((f) => (
                      <button
                        key={f}
                        onClick={() => setConstraintFilter(f)}
                        className={`rounded px-2 py-0.5 text-xs transition-colors ${
                          constraintFilter === f ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {{ all: "すべて", pending: "承認待ち", active: "有効", dismissed: "却下" }[f]}
                      </button>
                    ))}
                  </div>
                </div>

                {filteredConstraints.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center border rounded-lg">条件がありません</p>
                ) : (
                  <div className="divide-y rounded-lg border overflow-hidden">
                    {filteredConstraints.map((c) => (
                      <div key={c.id} className={`flex items-start gap-3 px-4 py-3 text-sm ${c.status === "pending" ? "bg-amber-50 dark:bg-amber-950/10" : ""}`}>
                        <div className="flex-1 min-w-0">
                          <p className="break-words">{c.content}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            {statusLabel[c.status]} · {c.source === "ai" ? "AI抽出" : "手動"}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {c.status === "pending" && (
                            <>
                              <button onClick={() => handleConstraintStatus(c.id, "active")} className="rounded p-1 text-green-600 hover:bg-green-50 dark:hover:bg-green-950/20" title="承認">
                                <Check className="h-3.5 w-3.5" />
                              </button>
                              <button onClick={() => handleConstraintStatus(c.id, "dismissed")} className="rounded p-1 text-muted-foreground hover:bg-muted" title="却下">
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </>
                          )}
                          {c.status === "dismissed" && (
                            <button onClick={() => handleConstraintStatus(c.id, "active")} className="rounded px-1.5 py-0.5 text-[10px] text-muted-foreground border hover:bg-muted" title="復元">
                              復元
                            </button>
                          )}
                          <button onClick={() => handleConstraintDelete(c.id)} className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10" title="削除">
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 手動追加 */}
                <div className="mt-3 flex gap-2">
                  <input
                    className="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="手動で条件を追加（例: 予算超過は必ず事前報告すること）"
                    value={newConstraintText}
                    onChange={(e) => setNewConstraintText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleAddConstraint(); } }}
                  />
                  <button
                    onClick={handleAddConstraint}
                    disabled={addingConstraint || !newConstraintText.trim()}
                    className="flex items-center gap-1 rounded-md bg-primary text-primary-foreground px-3 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    追加
                  </button>
                </div>
              </section>

              {/* 定性方針 */}
              <section>
                <h2 className="text-base font-semibold mb-1">定性方針</h2>
                <p className="text-xs text-muted-foreground mb-3">
                  AIが抽出・更新するCEOの判断傾向テキストです。手動で編集することもできます（200〜400文字目安）。
                </p>
                <textarea
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  rows={8}
                  value={qualitativeText}
                  onChange={(e) => setQualitativeText(e.target.value)}
                  placeholder="過去の会話から学習すると自動入力されます。"
                />
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={handleSaveQualitative}
                    disabled={savingQualitative || !isQualitativeDirty}
                    className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {savingQualitative ? "保存中..." : "保存"}
                  </button>
                  {qualitativeSaveMsg && (
                    <span className={`text-sm ${qualitativeSaveMsg.includes("失敗") ? "text-destructive" : "text-green-600"}`}>
                      {qualitativeSaveMsg}
                    </span>
                  )}
                </div>
              </section>

            </div>
          )}
        </div>
      )}
    </div>
  );
}
