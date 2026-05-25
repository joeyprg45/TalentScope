function formatId(id: string): string {
  return id.includes("@") ? id.split("@")[0] : id;
}

export function getToolLabel(toolName: string, args?: Record<string, string>): string {
  switch (toolName) {
    case "MemberPlugin-list_all_members":
      return "全メンバー一覧を取得";
    case "MemberPlugin-get_member_detail":
      return args?.member_id ? `${formatId(args.member_id)} の詳細を確認` : "メンバー詳細を確認";
    case "MemberPlugin-find_members_by_skill":
      return args?.skill_name ? `「${args.skill_name}」スキルで絞り込み` : "スキルで候補を絞り込み";
    case "MemberPlugin-get_member_schedule":
      return args?.member_id ? `${formatId(args.member_id)} のスケジュールを確認` : "スケジュールを確認";
    case "ProjectPlugin-list_all_projects":
      return args?.status_filter ? `${args.status_filter} プロジェクト一覧を取得` : "プロジェクト一覧を取得";
    case "ProjectPlugin-get_project_detail":
      return "プロジェクト要件を取得";
    case "ProjectPlugin-find_project_by_name":
      return args?.name ? `「${args.name}」プロジェクトを検索` : "プロジェクトを検索";
    case "ContributionPlugin-get_member_task_stats":
      return args?.member_id ? `${formatId(args.member_id)} のタスク実績を分析` : "タスク実績を分析";
    case "ContributionPlugin-calc_project_cost":
      return "プロジェクトコストを試算";
    case "ContributionPlugin-get_project_tasks":
      return "プロジェクトタスクを取得";
    case "MeetingPlugin-get_member_meeting_analyses":
      return args?.member_id ? `${formatId(args.member_id)} の議事録を評価` : "議事録を評価";
    case "MeetingPlugin-get_project_meeting_summaries":
      return "会議サマリーを取得";
    case "TeamBalancePlugin-evaluate_team_balance":
      return "チームバランスを評価";
    case "SynergyPlugin-get_collaboration_matrix":
      return "コラボレーション実績を分析";
    default:
      return toolName;
  }
}
