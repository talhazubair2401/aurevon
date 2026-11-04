import styles from "./page.module.css";

// M1 foundation page. Staff sign-in, sessions and roles are built in M2 (MTS v2.1 §9, §16).
export default function StaffHomePage() {
  return (
    <main className={styles.main}>
      <section className={styles.card} aria-labelledby="staff-title">
        <h1 id="staff-title" className={styles.title}>
          AureVon Staff
        </h1>
        <p className={styles.note}>Staff sign-in arrives in milestone M2.</p>
      </section>
    </main>
  );
}
