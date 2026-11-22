/** Tên người dùng (nếu có) kèm email bên dưới; dùng chung cho các danh sách có cột chủ sở hữu. */
export function UserCell({ name, email }: { name?: string | null; email: string }) {
  return name ? <>{name}<div className="small muted">{email}</div></> : <>{email}</>;
}
