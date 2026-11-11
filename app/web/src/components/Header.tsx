import React from 'react';

export type ActiveTab = 'customer' | 'seller' | 'operator';

interface HeaderProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  onOpenBreakIt: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, onTabChange, onOpenBreakIt }) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <span className="brand-title">ReturnLens</span>
        <span className="store-badge">Dhun Audio · Bengaluru</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
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
            Operator Controls
          </button>
        </nav>

        <button
          type="button"
          onClick={onOpenBreakIt}
          className="btn-danger"
          style={{ padding: '6px 12px', fontSize: '12px', fontWeight: 700 }}
          title="Open Judge Attack Sandbox (23 W1)"
        >
          ⚡ Try to Break It
        </button>
      </div>
    </header>
  );
};
