import styles from "./page.module.css";

// M1 foundation page. The approved homepage design is built in M4 (MTS v2.1 §16).
export default function HomePage() {
  return (
    <main className={styles.main}>
      <div>
        <h1 className={styles.wordmark}>AUREVON</h1>
        <p className={styles.tagline}>Modern Style. Timeless Confidence.</p>
        <hr className={styles.rule} />
      </div>
    </main>
  );
}
