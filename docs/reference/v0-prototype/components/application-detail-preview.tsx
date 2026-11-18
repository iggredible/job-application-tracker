"use client"

// Next.js needs a client boundary; the Vite components themselves stay directive-free.
import { useState } from "react"

import ApplicationDetail from "@/components/application-detail"
import ApplicationsList from "@/components/applications-list"
import BaseResume from "@/components/base-resume"
import Insights from "@/components/insights"

const pages = ["Applications", "Resume", "Insights"] as const
type Page = (typeof pages)[number]

export default function ApplicationDetailPreview() {
  const [page, setPage] = useState<Page>("Applications")
  const [openId, setOpenId] = useState<string | null>(null)

  function handleNavigate(label: string) {
    if (!pages.includes(label as Page)) return
    setOpenId(null)
    setPage(label as Page)
  }

  if (page === "Resume") {
    return <BaseResume onNavigate={handleNavigate} />
  }

  if (page === "Insights") {
    return <Insights onNavigate={handleNavigate} />
  }

  if (openId) {
    return <ApplicationDetail onBack={() => setOpenId(null)} onNavigate={handleNavigate} />
  }

  return <ApplicationsList onOpenApplication={setOpenId} onNavigate={handleNavigate} />
}
