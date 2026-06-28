import React from 'react';

type GeoButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface GeoButtonProps {
  variant?: GeoButtonVariant;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
}

export const GeoButton: React.FC<GeoButtonProps> = ({
  variant = 'primary',
  children,
  onClick,
  disabled = false,
  className = '',
  type = 'button',
}) => {
  const baseStyles = `
    font-family: var(--font-label);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 8px 16px;
    transition: all 150ms ease;
    cursor: pointer;
    border: none;
    outline: none;
  `;

  const variantStyles: Record<GeoButtonVariant, string> = {
    primary: `
      background-color: var(--signal-info);
      color: #000;
      font-weight: 600;
    `,
    secondary: `
      background-color: transparent;
      color: var(--text-secondary);
      border: 1px solid var(--geoint-border);
      font-weight: 500;
    `,
    danger: `
      background-color: var(--signal-critical);
      color: #fff;
      font-weight: 600;
    `,
    ghost: `
      background-color: transparent;
      color: var(--text-secondary);
      font-weight: 500;
    `,
  };

  const hoverStyles: Record<GeoButtonVariant, string> = {
    primary: `
      &:hover:not(:disabled) {
        background-color: var(--sentiment-partner);
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
      }
    `,
    secondary: `
      &:hover:not(:disabled) {
        border-color: var(--text-tertiary);
        color: var(--text-primary);
        background-color: var(--geoint-elevated);
      }
    `,
    danger: `
      &:hover:not(:disabled) {
        background-color: var(--sentiment-adversary);
        box-shadow: 0 0 16px rgba(239, 68, 68, 0.5);
      }
    `,
    ghost: `
      &:hover:not(:disabled) {
        color: var(--text-primary);
        background-color: var(--geoint-elevated);
      }
    `,
  };

  const disabledStyles = `
    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
  `;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${hoverStyles[variant]} ${disabledStyles} ${className}`}
      style={{
        fontFamily: 'var(--font-label)',
      }}
    >
      {children}
    </button>
  );
};
