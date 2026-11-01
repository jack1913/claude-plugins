export function Address({ register }) {
  const [shown] = useState<string>("");
  navigator.serviceWorker.register("/sw.js");
  return <input {...register("address.street")} />;
}
