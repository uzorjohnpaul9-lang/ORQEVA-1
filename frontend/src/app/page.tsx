'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        const raw = localStorage.getItem('sb-' + process.env.NEXT_PUBLIC_SUPABASE_URL?.split('//')[1]?.split('.')[0] + '-auth-token') || localStorage.getItem('orqeva_token');
        if (raw) {
          router.replace('/dashboard');
          return;
        }
      }
    } catch (e) {}
    router.replace('/login');
  }, [router]);

  return (
    <div className='min-h-screen flex items-center justify-center bg-bg-primary'>
      <div className='text-sm text-text-secondary'>Loading...</div>
    </div>
  );
}
