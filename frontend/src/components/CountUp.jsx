import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { useEffect } from "react";
export default function CountUp({ value, prefix = "$", className = "" }) {
  const reduce=useReducedMotion(), count=useMotionValue(reduce?value:0), rounded=useTransform(count,v=>`${prefix}${Math.round(v).toLocaleString()}`);
  useEffect(()=>{if(reduce){count.set(value);return}const controls=animate(count,value,{duration:.35,ease:"easeOut"});return controls.stop},[value,reduce,count]);
  return <motion.span className={`tabular ${className}`}>{rounded}</motion.span>;
}
