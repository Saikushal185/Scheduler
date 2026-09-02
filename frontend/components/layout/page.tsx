"use client";

import * as React from "react";

/** Sets the title shown in the top bar from within a page. */
const PageMetaContext = React.createContext<{
  setMeta: (meta: { title: string; description?: string; actions?: React.ReactNode }) => void;
}>({ setMeta: () => undefined });

export function usePageMeta(
  title: string,
  description?: string,
  actions?: React.ReactNode,
  deps: unknown[] = [],
) {
  const { setMeta } = React.useContext(PageMetaContext);
  React.useEffect(() => {
    setMeta({ title, description, actions });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, description, ...deps]);
}

export const PageMetaProvider = PageMetaContext.Provider;

export function PageSection({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      {title ? (
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
            {description ? (
              <p className="text-xs text-slate-500">{description}</p>
            ) : null}
          </div>
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}
