import { FeaturedGames } from "@/components/home-sections";
import { HomeSlider } from "@/components/home-slider";
import { ReferBanner } from "@/components/refer-banner";
import { CouponClaim } from "@/components/coupon-claim";

export default function HomePage() {
  return (
    <>
      <HomeSlider />
      <ReferBanner />
      <FeaturedGames />
      <CouponClaim />
    </>
  );
}
