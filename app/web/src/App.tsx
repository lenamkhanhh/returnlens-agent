import React, { useState } from 'react';
import { Header, ActiveTab } from './components/Header';
import { CustomerView } from './components/CustomerView/CustomerView';
import { SellerView } from './components/SellerView/SellerView';
import { OperatorView } from './components/OperatorView/OperatorView';
import { BreakItModal } from './components/BreakIt/BreakItModal';

export const App: React.FC = () => {
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initialTab = (urlParams?.get('tab') as ActiveTab) || 'customer';
  const initialBreakIt = urlParams?.get('modal') === 'breakit';

  const [activeTab, setActiveTab] = useState<ActiveTab>(initialTab);
  const [isBreakItOpen, setIsBreakItOpen] = useState(initialBreakIt);

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
