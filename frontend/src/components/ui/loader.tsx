import React from 'react';

interface LoaderProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  colors?: {
    primary?: string;
    secondary?: string;
    accent?: string;
    background?: string;
  };
  className?: string;
  showCornerDots?: boolean;
  barCount?: number;
}

const Loader: React.FC<LoaderProps> = ({
  size = 'md',
  colors = {},
  className = '',
  showCornerDots = true,
  barCount = 4
}) => {
  const {
    primary = 'blue-500',
    secondary = 'purple-500',
    accent = 'cyan-500',
    background = 'gray-900'
  } = colors;

  const sizeClasses = {
    sm: 'w-16 h-16',
    md: 'w-32 h-32',
    lg: 'w-48 h-48',
    xl: 'w-64 h-64'
  };

  const barHeightClasses = {
    sm: 'h-6',
    md: 'h-12',
    lg: 'h-18',
    xl: 'h-24'
  };

  const dotSizeClasses = {
    sm: 'w-1 h-1',
    md: 'w-2 h-2',
    lg: 'w-3 h-3',
    xl: 'w-4 h-4'
  };

  const generateBars = () => {
    const bars = [];
    const colors = [accent, primary, 'indigo-500', secondary];
    
    for (let i = 0; i < barCount; i++) {
      const color = colors[i % colors.length];
      const delay = i * 0.1;
      
      bars.push(
        <div
          key={i}
          className={`w-1.5 ${barHeightClasses[size]} bg-${color} rounded-full animate-[bounce_1s_ease-in-out_infinite_${delay}s]`}
          style={{ animationDelay: `${delay}s` }}
        />
      );
    }
    
    return bars;
  };

  return (
    <div className={`${sizeClasses[size]} relative flex items-center justify-center ${className}`}>
      {/* Outer glow */}
      <div className={`absolute inset-0 rounded-xl bg-${primary}/20 blur-xl animate-pulse`} />
      
      {/* Main container */}
      <div className="w-full h-full relative flex items-center justify-center">
        {/* Spinning gradient border */}
        <div className={`absolute inset-0 rounded-xl bg-gradient-to-r from-${accent} via-${primary} to-${secondary} animate-spin blur-sm`} />
        
        {/* Inner content area */}
        <div className={`absolute inset-1 bg-${background} rounded-lg flex items-center justify-center overflow-hidden`}>
          {/* Animated bars */}
          <div className="flex gap-1 items-center">
            {generateBars()}
          </div>
          
          {/* Overlay gradient */}
          <div className={`absolute inset-0 bg-gradient-to-t from-transparent via-${primary}/10 to-transparent animate-pulse`} />
        </div>
      </div>
      
      {/* Corner dots */}
      {showCornerDots && (
        <>
          <div className={`absolute -top-1 -left-1 ${dotSizeClasses[size]} bg-${primary} rounded-full animate-ping`} />
          <div className={`absolute -top-1 -right-1 ${dotSizeClasses[size]} bg-${secondary} rounded-full animate-ping`} style={{ animationDelay: '0.1s' }} />
          <div className={`absolute -bottom-1 -left-1 ${dotSizeClasses[size]} bg-${accent} rounded-full animate-ping`} style={{ animationDelay: '0.2s' }} />
          <div className={`absolute -bottom-1 -right-1 ${dotSizeClasses[size]} bg-${primary} rounded-full animate-ping`} style={{ animationDelay: '0.3s' }} />
        </>
      )}
    </div>
  );
};

// Demo component to showcase different variations
const LoaderDemo: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-8 text-center">
          Reusable Loader Component
        </h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
          {/* Default */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">Default (Medium)</h3>
            <Loader />
          </div>
          
          {/* Small size */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">Small Size</h3>
            <Loader size="sm" />
          </div>
          
          {/* Large size */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">Large Size</h3>
            <Loader size="lg" />
          </div>
          
          {/* Custom colors */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">Custom Colors</h3>
            <Loader 
              colors={{
                primary: 'emerald-500',
                secondary: 'rose-500',
                accent: 'yellow-500',
                background: 'slate-800'
              }}
            />
          </div>
          
          {/* No corner dots */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">No Corner Dots</h3>
            <Loader showCornerDots={false} />
          </div>
          
          {/* More bars */}
          <div className="bg-gray-800 rounded-lg p-6 flex flex-col items-center">
            <h3 className="text-white font-semibold mb-4">6 Bars</h3>
            <Loader barCount={6} />
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-white font-semibold mb-4">Usage Examples</h3>
          <div className="bg-gray-900 rounded p-4 overflow-x-auto">
            <pre className="text-green-400 text-sm whitespace-pre-wrap">
{`// Basic usage
<Loader />

// Small size with custom colors
<Loader 
  size="sm" 
  colors={{ primary: 'red-500', accent: 'pink-500' }} 
/>

// Large loader without corner dots
<Loader 
  size="lg" 
  showCornerDots={false} 
  barCount={6}
/>

// With custom CSS classes
<Loader 
  className="my-4 mx-auto" 
  colors={{ background: 'slate-700' }}
/>`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoaderDemo;