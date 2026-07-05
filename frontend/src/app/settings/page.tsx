'use client'

import { useState, useEffect } from 'react'
import { Save, User, Key, Bell } from 'lucide-react'
import toast from 'react-hot-toast'
import { getProfile, updateProfile } from '@/lib/api'

export default function SettingsPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<any>(null)

  useEffect(() => {
    getProfile().then(p => {
      setProfile(p)
      setName(p.name || '')
      setEmail(p.email || '')
    }).catch(() => toast.error('Failed to load profile'))
  }, [])

  const handleSave = async () => {
    setLoading(true)
    try {
      await updateProfile(name, email)
      toast.success('Profile updated!')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Update failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Manage your account settings</p>
      </div>

      <div className="space-y-6">
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10">
              <User className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Profile</h2>
              <p className="text-xs text-slate-400">Update your personal information</p>
            </div>
          </div>
          <div className="space-y-4">
            <div>
              <label className="label">Name</label>
              <input className="input-field" value={name} onChange={e => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input-field" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <button onClick={handleSave} disabled={loading} className="btn-primary">
              {loading ? 'Saving...' : <span className="flex items-center gap-2"><Save className="h-4 w-4" /> Save Changes</span>}
            </button>
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10">
              <Key className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">API Keys</h2>
              <p className="text-xs text-slate-400">Manage your API keys for integrations</p>
            </div>
          </div>
          <a href="/api-keys" className="text-indigo-400 hover:text-indigo-300 text-sm font-medium">
            Manage API Keys →
          </a>
        </div>

        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-500/10">
              <Bell className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Billing & Plan</h2>
              <p className="text-xs text-slate-400">Manage your subscription and credits</p>
            </div>
          </div>
          <a href="/billing" className="text-indigo-400 hover:text-indigo-300 text-sm font-medium">
            View Billing →
          </a>
        </div>
      </div>
    </div>
  )
}
