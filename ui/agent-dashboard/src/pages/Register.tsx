import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { OAuthButtons } from '@/components/Auth/OAuthButtons';
import { useAuth } from '@/hooks/useAuth';
import { CheckCircle2 } from 'lucide-react';

export function Register() {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const { register, isLoading } = useAuth();
  const navigate = useNavigate();

  // Password strength validation
  const validatePassword = (password: string): string | null => {
    if (password.length < 8) {
      return 'Password must be at least 8 characters long';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter';
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter';
    }
    if (!/[0-9]/.test(password)) {
      return 'Password must contain at least one number';
    }
    return null;
  };

  // Email validation
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate email
    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    // Validate display name
    if (displayName.trim().length < 2) {
      setError('Display name must be at least 2 characters long');
      return;
    }

    if (displayName.trim().length > 50) {
      setError('Display name must not exceed 50 characters');
      return;
    }

    // Validate password
    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    // Validate password confirmation
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      await register(email, password, displayName.trim());
      setSuccess(true);
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login', { state: { email } });
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    }
  };

  // Show success message after registration
  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="pt-6 text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-green-500/10 rounded-full flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-green-500" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-white">Check your email</h2>
                <p className="text-slate-400">
                  We've sent a verification link to <span className="font-medium text-white">{email}</span>
                </p>
                <p className="text-sm text-slate-500">
                  Click the link in the email to verify your account. You'll be redirected to login shortly.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link to="/" className="flex items-center justify-center gap-2 mb-8">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg" />
          <span className="font-bold text-2xl text-white">TradeStream</span>
        </Link>

        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle className="text-2xl text-white">Create an account</CardTitle>
            <CardDescription className="text-slate-400">
              Get started with TradeStream for free
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* OAuth buttons */}
            <OAuthButtons />

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-slate-800 px-2 text-slate-500">Or continue with</span>
              </div>
            </div>

            {/* Registration form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-300">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={isLoading}
                  className="bg-slate-900 border-slate-600 text-white placeholder:text-slate-500"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="displayName" className="text-slate-300">Display Name</Label>
                <Input
                  id="displayName"
                  type="text"
                  placeholder="Your name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  disabled={isLoading}
                  minLength={2}
                  maxLength={50}
                  className="bg-slate-900 border-slate-600 text-white placeholder:text-slate-500"
                />
                <p className="text-xs text-slate-500">
                  This is how you'll appear to other users
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-300">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  className="bg-slate-900 border-slate-600 text-white placeholder:text-slate-500"
                />
                <p className="text-xs text-slate-500">
                  At least 8 characters with uppercase, lowercase, and numbers
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-slate-300">Confirm Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  disabled={isLoading}
                  className="bg-slate-900 border-slate-600 text-white placeholder:text-slate-500"
                />
              </div>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? 'Creating account...' : 'Create account'}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex justify-center">
            <p className="text-sm text-slate-400">
              Already have an account?{' '}
              <Link to="/login" className="text-blue-400 hover:text-blue-300 font-medium">
                Sign in
              </Link>
            </p>
          </CardFooter>
        </Card>

        {/* Footer disclaimer */}
        <p className="text-xs text-slate-500 text-center mt-6">
          By creating an account, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  );
}
