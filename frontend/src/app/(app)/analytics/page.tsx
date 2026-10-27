"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const TARGET = "/portfolio/analytics";

function RedirectInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const qs = params.toString();
    router.replace(qs ? `${TARGET}?${qs}` : TARGET);
  }, [router, params]);

  return null;
}

export default function RedirectPage() {
  return (
    <Suspense fallback={null}>
      <RedirectInner />
    </Suspense>
  );
}