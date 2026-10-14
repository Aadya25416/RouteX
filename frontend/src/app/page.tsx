import LandingPage from "@/components/landing/LandingPage";
import HomeFooter from "@/components/home/HomeFooter";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      <LandingPage />
      <HomeFooter />
    </div>
  );
}
