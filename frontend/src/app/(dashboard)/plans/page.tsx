"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { CreditCard, Plus, Edit, ToggleLeft, ToggleRight } from "lucide-react";

interface Plan { id: number; name: string; slug: string; price: number; billing_cycle: string; max_users: number; is_active: boolean; created_at: string }

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", price: "", billing_cycle: "monthly", max_users: "5" });

  const load = () => { api.get("/admin/security/plans").then(({ data }) => { if (data.success) setPlans(data.plans); }).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/admin/security/plans", { ...form, price: parseFloat(form.price), max_users: parseInt(form.max_users) });
    setShowCreate(false); setForm({ name: "", slug: "", price: "", billing_cycle: "monthly", max_users: "5" }); load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-white">Plans</h1><p className="text-slate-400 text-sm mt-1">{plans.length} plans</p></div>
        <button onClick={() => setShowCreate(!showCreate)} className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition">
          <Plus className="w-4 h-4" /> New Plan
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 space-y-4">
          <h3 className="text-white font-semibold">Create Plan</h3>
          <div className="grid grid-cols-2 gap-4">
            <input placeholder="Plan Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 text-sm" required />
            <input placeholder="Slug" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 text-sm" required />
            <input placeholder="Price" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 text-sm" required />
            <select value={form.billing_cycle} onChange={(e) => setForm({ ...form, billing_cycle: e.target.value })} className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white focus:ring-2 focus:ring-blue-500 text-sm">
              <option value="monthly">Monthly</option><option value="yearly">Yearly</option><option value="one_time">One-time</option>
            </select>
            <input placeholder="Max Users" type="number" value={form.max_users} onChange={(e) => setForm({ ...form, max_users: e.target.value })} className="px-4 py-2.5 bg-slate-700/50 border border-slate-600/50 rounded-xl text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 text-sm" />
          </div>
          <div className="flex gap-3">
            <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium">Create</button>
            <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-sm">Cancel</button>
          </div>
        </form>
      )}

      {loading ? <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map((p) => (
            <div key={p.id} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 hover:border-blue-500/30 transition">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2"><CreditCard className="w-5 h-5 text-blue-400" /><h3 className="text-white font-semibold">{p.name}</h3></div>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${p.is_active ? "bg-green-500/20 text-green-400" : "bg-slate-500/20 text-slate-400"}`}>{p.is_active ? "Active" : "Inactive"}</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Price</span><span className="text-white font-semibold">${p.price}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Billing</span><span className="text-white">{p.billing_cycle}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Max Users</span><span className="text-white">{p.max_users}</span></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
