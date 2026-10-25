import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { checkHealth } from '../services/api';

/**
 * Navbar — Top navigation header with view switching and live API health badge.
 *
 * Requirements:
 *   - NavLink switching between '/' (Dashboard) and '/accuracy' (Accuracy)
 *   - Health badge with 5s timeout using AbortController on mount only
 *   - Green dot for 'API Live', Red dot for 'API Down'
 */
export function Navbar() {
  const [healthStatus, setHealthStatus] = useState<'checking' | 'ok' | 'err'>('checking');

  useEffect(() => {
    const controller = new AbortController();
    // 5-second timeout safeguard
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 5000);

    checkHealth(controller.signal)
      .then((res) => {
        clearTimeout(timeoutId);
        if (res && res.status === 'ok') {
          setHealthStatus('ok');
        } else {
          setHealthStatus('err');
        }
      })
      .catch(() => {
        setHealthStatus('err');
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []); // Runs once on mount only — no polling or retry loop

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <div className="navbar-brand">
            <span>GB Wind Power</span>
            <span className="brand-badge">Elexon BMRS</span>
          </div>

          <div className="navbar-nav">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `nav-link${isActive ? ' active' : ''}`
              }
              style={({ isActive }) => ({
                borderBottom: isActive ? '2px solid var(--color-forecast)' : '2px solid transparent',
                paddingBottom: '0.25rem',
                borderRadius: '0',
              })}
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/accuracy"
              className={({ isActive }) =>
                `nav-link${isActive ? ' active' : ''}`
              }
              style={({ isActive }) => ({
                borderBottom: isActive ? '2px solid var(--color-forecast)' : '2px solid transparent',
                paddingBottom: '0.25rem',
                borderRadius: '0',
              })}
            >
              Accuracy
            </NavLink>
          </div>
        </div>

        {/* Health Check Badge */}
        <div className="health-badge" title="Backend API Health Probe">
          <span
            className={`health-dot ${healthStatus === 'ok' ? 'ok' : 'err'}`}
            style={{
              backgroundColor: healthStatus === 'ok' ? 'var(--color-success)' : 'var(--color-danger)',
              boxShadow: healthStatus === 'ok' ? '0 0 6px var(--color-success)' : '0 0 6px var(--color-danger)',
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>
            {healthStatus === 'ok' ? 'API Live' : 'API Down'}
          </span>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
