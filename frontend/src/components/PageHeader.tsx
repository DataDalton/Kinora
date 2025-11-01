interface PageHeaderProps {
  title: string;
  description: string;
  gradientFrom?: string;
  gradientVia?: string;
  gradientTo?: string;
  children?: React.ReactNode;
}

const colorMap: Record<string, string> = {
  'blue-600/10': 'rgba(37, 99, 235, 0.1)',
  'indigo-600/10': 'rgba(79, 70, 229, 0.1)',
  'cyan-600/10': 'rgba(8, 145, 178, 0.1)',
  'pink-600/10': 'rgba(219, 39, 119, 0.1)',
  'orange-600/10': 'rgba(234, 88, 12, 0.1)',
  'emerald-600/10': 'rgba(5, 150, 105, 0.1)',
  'green-600/10': 'rgba(22, 163, 74, 0.1)',
  'yellow-600/10': 'rgba(202, 138, 4, 0.1)',
  'slate-600/10': 'rgba(71, 85, 105, 0.1)',
  'violet-600/10': 'rgba(124, 58, 237, 0.1)',
  'purple-600/10': 'rgba(147, 51, 234, 0.1)',
  'red-600/10': 'rgba(220, 38, 38, 0.1)',
  'gray-600/10': 'rgba(75, 85, 99, 0.1)',
  'amber-600/10': 'rgba(217, 119, 6, 0.1)',
  'teal-600/10': 'rgba(13, 148, 136, 0.1)',
  'fuchsia-600/10': 'rgba(192, 38, 211, 0.1)',
  'zinc-600/10': 'rgba(82, 82, 91, 0.1)',
};

export default function PageHeader({
  title,
  description,
  gradientFrom = 'slate-600/10',
  gradientVia = 'gray-600/10',
  gradientTo = 'zinc-600/10',
  children,
}: PageHeaderProps) {
  const fromColor = colorMap[gradientFrom] || colorMap['slate-600/10'];
  const viaColor = colorMap[gradientVia] || colorMap['gray-600/10'];
  const toColor = colorMap[gradientTo] || colorMap['zinc-600/10'];

  const gradientStyle = {
    backgroundImage: `linear-gradient(to right, ${fromColor}, ${viaColor}, ${toColor})`,
  };

  return (
    <div style={gradientStyle} className="border-b-2 border-border">
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
