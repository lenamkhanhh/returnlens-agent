import React, { useState, useEffect } from 'react';
import { Header, ActiveTab } from './components/Header';
import { CustomerView } from './components/CustomerView/CustomerView';
import { SellerView } from './components/SellerView/SellerView';
import { OperatorView } from './components/OperatorView/OperatorView';
import { BreakItModal } from './components/BreakIt/BreakItModal';
import { resolveDemoScale } from './utils/demoScale';

export const App: React.FC = () => {
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initialTab = (urlParams?.get('tab') as ActiveTab) || 'customer';
  const initialBreakIt = urlParams?.get('modal') === 'breakit';

  const [activeTab, setActiveTab] = useState<ActiveTab>(initialTab);
  const [isBreakItOpen, setIsBreakItOpen] = useState(initialBreakIt);

  // Wave 11: Demo mode scaling (?demo=1 or ?scale=1.35) for 1080p recording readability
  const activeScale = resolveDemoScale(
    typeof window !== 'undefined' ? window.location.search : '',
    typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('returnlens_demo_scale') : null
  );

  useEffect(() => {
    if (activeScale && activeScale > 1) {
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('returnlens_demo_scale', String(activeScale));
      }
      document.documentElement.classList.add('demo-mode');
      document.body.classList.add('demo-mode');
      (document.body.style as any).zoom = `${activeScale}`;
      document.documentElement.style.setProperty('--demo-scale', `${activeScale}`);
    } else {
      if (typeof sessionStorage !== 'undefined' && urlParams?.get('demo') === '0') {
        sessionStorage.removeItem('returnlens_demo_scale');
      }
      document.documentElement.classList.remove('demo-mode');
      document.body.classList.remove('demo-mode');
      (document.body.style as any).zoom = '';
      document.documentElement.style.removeProperty('--demo-scale');
    }
  }, [activeScale]);

  return (
    <div>
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenBreakIt={() => setIsBreakItOpen(true)}
      />

      <main className="main-content">
        {activeTab === 'customer' && <CustomerView />}
        {activeTab === 'seller' && <SellerView />}
        {activeTab === 'operator' && <OperatorView />}
      </main>

      <BreakItModal
        isOpen={isBreakItOpen}
        onClose={() => setIsBreakItOpen(false)}
      />
    </div>
  );
};

export default App;
