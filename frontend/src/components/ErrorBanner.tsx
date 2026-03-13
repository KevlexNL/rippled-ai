export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mx-4 my-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
      {message}
    </div>
  )
}
