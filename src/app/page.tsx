'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

const LAST_PATH_KEY = 'tradybull-last-path';
const DEFAULT_PATH = '/strategy/backtesting/overview';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const lastPath = localStorage.getItem(LAST_PATH_KEY);
    router.replace(lastPath || DEFAULT_PATH);
  }, [router]);

  return null;
}
