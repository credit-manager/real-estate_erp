"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Shield, AlertTriangle, Users, Activity, Lock, Unlock, XCircle } from "lucide-react";

interface SecSummary { login_failures_24h: number; login_success_24h: number; critical_events_7d: number; active_sessions: number }
interface SecEvent { id: number; event_type: string; master_user_email: string; ip: string; severity: string; details: any; created_at: string }

export default function SecurityPage() {
  const [summary, setSummary] = useState<SecSummary | null>(null);
  const [events, setEvents] = useState<SecEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/admin/security/security/summary"),
      api.get("/admin/security/security/events?limit=20"),
    ]).then(([s, e]) => {
      if (s.data.success) setSummary(s.data);
      if (e.data.success) setEvents(e.data.events);
    }).finally(() => setLoading(false));
  }, []);

  const killAll = async () => {
    if (!confirm("Kill ALL sessions (except yours)?")) return;
    await api.post("/admin/security/security/kill-all-sessions");
    const { data } = await api.get("/admin/security/security/summary");
    if (data.success) setSummary(data);
  };

  if (loading) return <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Security Center</h1>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2"><Activity className="w-4 h-4 text-green-400" /><span className="text-slate-400 text-sm">Logins (24h)</span></div>
            <p className="text-2xl font-bold text-white">{summary.login_success_24h}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2"><AlertTriangle className="w-4 h-4 text-red-400" /><span className="text-slate-400 text-sm">Failures (24h)</span></div>
            <p className={`text-2xl font-bold ${summary.login_failures_24h > 0 ? "text-red-400" : "text-white"}`}>{summary.login_failures_24h}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2"><Shield className="w-4 h-4 text-amber-400" /><span className="text-slate-400 text-sm">Critical (7d)</span></div>
            <p className={`text-2xl font-bold ${summary.critical_events_7d > 0 ? "text-amber-400" : "text-white"}`}>{summary.critical_events_7d}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2"><Users className="w-4 h-4 text-blue-400" /><span className="text-slate-400 text-sm">Active Sessions</span></div>
            <p className="text-2xl font-bold text-white">{summary.active_sessions}</p>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={killAll} className="flex items-center gap-2 px-4 py-2.5 bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400 rounded-xl text-sm font-medium transition">
          <XCircle className="w-4 h-4" /> Kill All Sessions
        </button>
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Security Events</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700/50">
                <th className="text-right py-3 px-3">Event</th>
                <th className="text-right py-3 px-3">User</th>
                <th className="text-right py-3 px-3">IP</th>
                <th className="text-right py-3 px-3">Severity</th>
                <th className="text-right py-3 px-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                  <td className="py-3 px-3 text-white font-medium">{e.event_type}</td>
                  <td className="py-3 px-3 text-slate-300">{e.master_user_email || "—"}</td>
                  <td className="py-3 px-3 text-slate-400 font-mono text-xs">{e.ip || "—"}</td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${e.severity === "critical" ? "bg-red-500/20 text-red-400" : e.severity === "warning" ? "bg-amber-500/20 text-amber-400" : "bg-blue-500/20 text-blue-400"}`}>
                      {e.severity}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-slate-500 text-xs">{e.created_at?.replace("T", " ")?.slice(0, 19)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
