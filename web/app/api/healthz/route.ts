import { NextResponse } from "next/server";

// The dashboard is a service too: it participates in the Phase 0 health-check
// sweep like every backend service.
export function GET() {
  return NextResponse.json({ status: "ok", service: "web" });
}
