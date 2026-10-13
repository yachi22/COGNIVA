import React from "react";

export interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = "",
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-8 sm:p-10 border border-dashed border-border rounded-xl bg-surface/50 ${className}`}
    >
      <div className="w-10 h-10 rounded-lg bg-panel border border-border flex items-center justify-center text-secondary mb-3">
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-primary mb-1">{title}</h3>
      <p className="text-xs text-secondary max-w-sm mb-4 leading-relaxed">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};

export default EmptyState;
