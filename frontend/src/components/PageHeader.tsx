interface PageHeaderProps {
  title: string;
  description: string;
  gradientFrom?: string;
  gradientVia?: string;
  gradientTo?: string;
  children?: React.ReactNode;
}

export default function PageHeader({
  title,
  description,
  gradientFrom = 'slate-600/10',
  gradientVia = 'gray-600/10',
  gradientTo = 'zinc-600/10',
  children,
}: PageHeaderProps) {
  return (
    <div className={`bg-gradient-to-r from-${gradientFrom} via-${gradientVia} to-${gradientTo} border-b-2 border-border`}>
      <div className="container mx-auto px-6 py-8">
        <div className={children ? "flex justify-between items-start" : ""}>
          <div>
            <h1 className="text-4xl font-bold mb-2">{title}</h1>
            <p className="text-muted-foreground">{description}</p>
          </div>
          {children && <div className="flex gap-2">{children}</div>}
        </div>
      </div>
    </div>
  );
}
