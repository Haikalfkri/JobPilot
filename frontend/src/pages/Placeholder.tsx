type Props = { title: string; next: string }

export function Placeholder({ title, next }: Props) {
  return (
    <section className="placeholder">
      <h1>{title}</h1>
      <p>{next}</p>
    </section>
  )
}