import { useMotionTemplate, useMotionValue, motion } from "framer-motion";
import { type CSSProperties, type MouseEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface EvervaultCardProps {
  text?: string;
  className?: string;
  children?: ReactNode;
}

export function EvervaultCard({ text, className, children }: EvervaultCardProps) {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  function onMouseMove(event: MouseEvent<HTMLDivElement>) {
    const { left, top } = event.currentTarget.getBoundingClientRect();
    mouseX.set(event.clientX - left);
    mouseY.set(event.clientY - top);
  }

  return (
    <div className={cn("relative flex h-full w-full items-center justify-center bg-transparent p-0.5", className)}>
      <div onMouseMove={onMouseMove} className="group/card relative flex h-full w-full items-center justify-center overflow-hidden rounded-3xl bg-transparent">
        <CardPattern mouseX={mouseX} mouseY={mouseY} />
        <div className="relative z-10 flex items-center justify-center">
          <div className="relative flex h-44 w-44 items-center justify-center rounded-full text-center text-4xl font-bold text-white">
            <div className="absolute h-full w-full rounded-full bg-white/[0.8] blur-sm dark:bg-black/[0.8]" />
            <span className="relative z-20 px-5 leading-tight">{children || text}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function CardPattern({ mouseX, mouseY }: { mouseX: ReturnType<typeof useMotionValue<number>>; mouseY: ReturnType<typeof useMotionValue<number>> }) {
  const maskImage = useMotionTemplate`radial-gradient(250px at ${mouseX}px ${mouseY}px, white, transparent)`;
  const style = { maskImage, WebkitMaskImage: maskImage } as unknown as CSSProperties;

  return (
    <div className="pointer-events-none absolute inset-0">
      <div className="absolute inset-0 rounded-2xl [mask-image:linear-gradient(white,transparent)] group-hover/card:opacity-50" />
      <motion.div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-green-500 to-blue-700 opacity-0 backdrop-blur-xl transition duration-500 group-hover/card:opacity-100" style={style} />
    </div>
  );
}

export function Icon({ className, ...rest }: React.SVGProps<SVGSVGElement>) {
  return <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className={className} {...rest}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m6-6H6" /></svg>;
}
