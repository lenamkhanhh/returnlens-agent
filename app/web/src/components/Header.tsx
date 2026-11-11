import React from 'react';

export type ActiveTab = 'customer' | 'seller' | 'operator';

interface HeaderProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange }) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <span className="brand-title">ReturnLens</span>
        <span className="store-badge">Dhun Audio · Bengaluru</span>
      </div>

      <nav className="nav-tabs" aria-label="Console views">
        <button
          className={`tab-btn ${activeTab === 'customer' ? 'active' : ''}`}
          onClick={() => onTabChange('customer')}
        >
          Customer Portal
        </button>
        <button
          className={`tab-btn ${activeTab === 'seller' ? 'active' : ''}`}
          onClick={() => onTabChange('seller')}
        >
          Seller Console
        </button>
        <button
          className={`tab-btn ${activeTab === 'operator' ? 'active' : ''}`}
          onClick={() => onTabChange('operator')}
        >
          Operator (Wave 2)
        </button>
      </nav>
    </header>
  );
};
