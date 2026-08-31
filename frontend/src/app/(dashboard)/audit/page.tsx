"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { FileText, Filter } from "lucide-react";

interface AuditLog { id: number; action: string; master_user_email: string; resource_type: string; resource_id: number; old_value: string; new_value: string; result: string; ip: string; created_at: string }

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "50" });
    if (actionFilter) params.set("action", actionFilter);
    if (resourceFilter) params.set("resource_type", resourceFilter);
    api.get(`/admin/security/audit?${params}`).then(({ data }) => {
      if (data.success) setLogs(data.logs);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const actions = [...new Set(logs.map((l) => l.action))];
  const resources = [...new Set(logs.map((l) => l.resource_type))];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Audit Logs</h1>

      <div className="flex gap-3 items-center">
        <Filter className="w-4 h-4 text-slate-400" />
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}
          className="px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500">
          <option value="">All Actions</option>
          {actions.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={resourceFilter} onChange={(e) => setResourceFilter(e.target.value)}
          className="px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-xl text-white text-sm focus:ring-2 focus:ring-blue-500">
          <option value="">All Resources</option>
          {resources.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <button onClick={load} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm transition">Apply</button>
      </div>

      {loading ? <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div> : (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700/50">
                <th className="text-right py-3 px-4">Action</th>
                <th className="text-right py-3 px-4">User</th>
                <th className="text-right py-3 px-4">Resource</th>
                <th className="text-right py-3 px-4">Old</th>
                <th className="text-right py-3 px-4">New</th>
                <th className="text-right py-3 px-4">Result</th>
                <th className="text-right py-3 px-4">Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                  <td className="py-3 px-4 text-white font-medium">{l.action}</td>
                  <td className="py-3 px-4 text-slate-300 text-xs">{l.master_user_email}</td>
                  <td className="py-3 px-4 text-slate-400 text-xs">{l.resource_type}{l.resource_id ? `#${l.resource_id}` : ""}</td>
                  <td className="py-3 px-4 text-slate-500 text-xs max-w-[100px] truncate">{l.old_value || "—"}</td>
                  <td className="py-3 px-4 text-slate-500 text-xs max-w-[100px] truncate">{l.new_value || "—"}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${l.result === "SUCCESS" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>{l.result}</span>
                  </td>
                  <td className="py-3 px-4 text-slate-500 text-xs">{l.created_at?.replace("T", " ")?.slice(0, 19)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
