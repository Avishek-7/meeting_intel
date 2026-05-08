import React, { useEffect, useId, useRef, useState } from 'react';

interface AnimatedInputProps {
  label: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'tel';
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  onFocus?: (e: React.FocusEvent<HTMLInputElement>) => void;
  required?: boolean;
  disabled?: boolean;
  id?: string;
  className?: string;
  colors?: {
    text?: string;
    border?: string;
    focusText?: string;
    focusBorder?: string;
    background?: string;
  };
  size?: 'sm' | 'md' | 'lg';
  error?: string;
  success?: boolean;
}

const AnimatedInput: React.FC<AnimatedInputProps> = ({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  onBlur,
  onFocus,
  required = false,
  disabled = false,
  id,
  className = '',
  colors = {},
  size = 'md',
  error,
  success = false
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [hasValue, setHasValue] = useState(!!value);
  const inputRef = useRef<HTMLInputElement>(null);
  const generatedId = useId();
  const inputId = id ?? generatedId;

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHasValue(!!value);
  }, [value]);

  const {
    text = 'text-white',
    border = 'border-white',
    focusText = 'text-blue-400',
    focusBorder = 'border-blue-400',
    background = 'bg-transparent'
  } = colors;

  const sizeClasses = {
    sm: {
      padding: 'py-2',
      fontSize: 'text-sm'
    },
    md: {
      padding: 'py-4',
      fontSize: 'text-lg'
    },
    lg: {
      padding: 'py-5',
      fontSize: 'text-xl'
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setHasValue(!!newValue);
    onChange?.(newValue);
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    onFocus?.(e);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    onBlur?.(e);
  };

  const shouldAnimateLabel = isFocused || hasValue;
  const borderColor = error 
    ? 'border-red-500' 
    : success 
      ? 'border-green-500' 
      : shouldAnimateLabel 
        ? focusBorder 
        : border;

  const labelTextColor = error 
    ? 'text-red-500' 
    : success 
      ? 'text-green-500' 
      : shouldAnimateLabel 
        ? focusText 
        : text;

  // Split label into individual characters with staggered delays
  const renderAnimatedLabel = () => {
    return label.split('').map((char, index) => (
      <span
        key={index}
        className={`inline-block min-w-[5px] transition-all duration-300 ease-[cubic-bezier(0.68,-0.55,0.265,1.55)] ${labelTextColor} ${sizeClasses[size].fontSize}`}
        style={{
          transitionDelay: `${index * 50}ms`,
          transform: shouldAnimateLabel ? 'translateY(-30px)' : 'translateY(0)',
        }}
      >
        {char === ' ' ? '\u00A0' : char}
      </span>
    ));
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative mb-10">
        <input
          id={inputId}
          ref={inputRef}
          type={type}
          value={value}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          required={required}
          aria-required={required}
          disabled={disabled}
          placeholder={placeholder}
          className={`
            ${background} 
            border-0 
            border-b-2 
            ${borderColor}
            block 
            w-full 
            ${sizeClasses[size].padding}
            ${sizeClasses[size].fontSize}
            ${text}
            outline-none
            transition-colors
            duration-300
            disabled:opacity-50
            disabled:cursor-not-allowed
          `}
        />
        
        <label htmlFor={inputId} className={`absolute top-4 left-0 pointer-events-none ${size === 'sm' ? 'top-2' : size === 'lg' ? 'top-5' : 'top-4'}`}>
          {renderAnimatedLabel()}
        </label>
      </div>
      
      {error && (
        <p className="text-red-500 text-sm mt-1 absolute -bottom-6 left-0">
          {error}
        </p>
      )}
      
      {success && !error && (
        <div className="absolute -bottom-6 left-0">
          <span className="text-green-500 text-sm">✓ Valid</span>
        </div>
      )}
    </div>
  );
};

// Demo component showcasing different variations
const AnimatedInputDemo: React.FC = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    phone: ''
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleInputChange = (field: string) => (value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleBlur = (field: string, value: string) => {
    if (field === 'email' && value && !validateEmail(value)) {
      setErrors(prev => ({ ...prev, email: 'Please enter a valid email address' }));
    }
    if (field === 'password' && value && value.length < 6) {
      setErrors(prev => ({ ...prev, password: 'Password must be at least 6 characters' }));
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-8 text-center">
          Animated Input Component
        </h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
          {/* Default Input */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Default</h3>
            <AnimatedInput
              label="Username"
              value={formData.username}
              onChange={handleInputChange('username')}
              required
            />
          </div>

          {/* Email with validation */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Email Validation</h3>
            <AnimatedInput
              label="Email Address"
              type="email"
              value={formData.email}
              onChange={handleInputChange('email')}
              onBlur={(e) => handleBlur('email', e.target.value)}
              error={errors.email}
              success={Boolean(formData.email && validateEmail(formData.email))}
              required
            />
          </div>

          {/* Password */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Password</h3>
            <AnimatedInput
              label="Password"
              type="password"
              value={formData.password}
              onChange={handleInputChange('password')}
              onBlur={(e) => handleBlur('password', e.target.value)}
              error={errors.password}
              success={Boolean(formData.password && formData.password.length >= 6)}
              required
            />
          </div>

          {/* Small size */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Small Size</h3>
            <AnimatedInput
              label="Phone"
              type="tel"
              size="sm"
              value={formData.phone}
              onChange={handleInputChange('phone')}
            />
          </div>

          {/* Large size with custom colors */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Large Custom Colors</h3>
            <AnimatedInput
              label="Company Name"
              size="lg"
              colors={{
                text: 'text-purple-200',
                border: 'border-purple-400',
                focusText: 'text-purple-300',
                focusBorder: 'border-purple-300'
              }}
            />
          </div>

          {/* Disabled state */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-white font-semibold mb-4">Disabled</h3>
            <AnimatedInput
              label="Disabled Field"
              value="Cannot edit this"
              disabled
            />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-white font-semibold mb-4">Usage Examples</h3>
          <div className="bg-gray-900 rounded p-4 overflow-x-auto">
            <pre className="text-green-400 text-sm whitespace-pre-wrap">
{`// Basic usage
<AnimatedInput
  label="Username"
  value={username}
  onChange={setUsername}
  required
/>

// Email with validation
<AnimatedInput
  label="Email"
  type="email"
  value={email}
  onChange={setEmail}
  error={emailError}
  success={isValidEmail}
/>

// Custom styling
<AnimatedInput
  label="Custom Field"
  size="lg"
  colors={{
    text: 'text-emerald-200',
    focusText: 'text-emerald-400',
    border: 'border-emerald-500'
  }}
/>

// Password field
<AnimatedInput
  label="Password"
  type="password"
  value={password}
  onChange={setPassword}
  onBlur={validatePassword}
/>`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export { AnimatedInput };
export default AnimatedInputDemo;