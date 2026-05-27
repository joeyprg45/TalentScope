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
    case "ProjectPlugin-find_available_members":
      return args?.date_from
        ? `${args.date_from} 以降で稼働可能なメンバーを抽出`
        : "稼働可能なメンバーを抽出";
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
    case "MeetingPlugin-get_project_meetings":
      return "議事録本文を取得";
    case "MeetingPlugin-get_member_meetings":
      return args?.member_id ? `${formatId(args.member_id)} の議事録本文を取得` : "議事録本文を取得";
    case "TeamBalancePlugin-evaluate_team_balance":
      return "チームバランスを評価";
    case "TeamBalancePlugin-find_skill_gaps":
      return "スキル不足を検出";
    case "TeamBalancePlugin-compare_members":
      return "メンバーを横並び比較";
    case "SynergyPlugin-get_collaboration_matrix":
      return "コラボレーション実績を分析";
    case "SlackPlugin-get_slack_speaker_counts":
      return "Slack発言回数を集計";
    case "SlackPlugin-get_project_slack_messages":
      return "プロジェクトSlack本文を取得";
    case "SlackPlugin-get_member_slack_messages":
      return args?.member_id ? `${formatId(args.member_id)} のSlack発言を取得` : "Slack発言を取得";
    case "ClarificationPlugin-ask_user_clarification":
      return "ユーザーに逆質問";
    case "SubAgentPlugin-invoke_conversation_agent":
    case "SubAgentPlugin-invoke_task_agent":
    case "SubAgentPlugin-invoke_member_profiler":
    case "SubAgentPlugin-invoke_team_evaluator":
      return getSubAgentLabel(toolName.replace("SubAgentPlugin-", ""), args);
    default:
      return toolName;
  }
}

export function getSubAgentLabel(name: string, args?: Record<string, string>): string {
  switch (name) {
    case "invoke_conversation_agent":
      return args?.target_id
        ? `🤖 会話分析SA — ${formatId(args.target_id)}`
        : "🤖 会話分析サブエージェント";
    case "invoke_task_agent":
      return args?.target_id
        ? `🤖 タスク分析SA — ${formatId(args.target_id)}`
        : "🤖 タスク分析サブエージェント";
    case "invoke_member_profiler":
      return args?.member_id
        ? `🤖 プロファイラーSA — ${formatId(args.member_id)}`
        : "🤖 メンバープロファイラーSA";
    case "invoke_team_evaluator":
      return "🤖 チーム評価SA（ドラフトレビュー）";
    default:
      return `🤖 ${name}`;
  }
}
