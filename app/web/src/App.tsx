import React, { useState } from 'react';
import { Header, ActiveTab } from './components/Header';
import { CustomerView } from './components/CustomerView/CustomerView';
import { SellerView } from './components/SellerView/SellerView';
import { OperatorPlaceholder } from './components/OperatorView/OperatorPlaceholder';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('customer');

  return (
    <div>
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="main-content">
        {activeTab === 'customer' && <CustomerView />}
        {activeTab === 'seller' && <SellerView />}
        {activeTab === 'operator' && <OperatorPlaceholder />}
      </main>
    </div>
  );
};

export default App;
