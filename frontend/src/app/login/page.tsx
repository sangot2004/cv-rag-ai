import { LoginForm } from "@/features/auth/login-form";
export default async function Login({searchParams}: {searchParams: Promise<{reason?: string}>}) {
  return <LoginForm reason={(await searchParams).reason}/>;
}
