import json
import csv
from collections import defaultdict

def process_tweets(input_file):
    """Process tweet data to extract nodes and relationships"""
    with open(input_file, 'r', encoding='utf-8') as f:
        tweets = json.load(f)

    nodes = []
    relationships = []
    seen_ids = set()  # Track processed tweet IDs

    for tweet in tweets:
        main_tweet_id = tweet['url'].split('/')[-1].strip().lstrip("'")

        if main_tweet_id in seen_ids:
            continue

        seen_ids.add(main_tweet_id)
        nodes.append({
            'tweet_id': main_tweet_id,
            'username': tweet['username'],
            'timestamp': tweet['timestamp'],
            'date': tweet['date'],
            'content': tweet['content'],
            'url': tweet['url'],
            'level': 0
        })

        # Link to virtual ROOT node
        relationships.append({
            'start_id': main_tweet_id,
            'end_id': 'ROOT',
            'level': 0,
            'type': 'original'
        })

        process_replies(tweet.get('replies', []), main_tweet_id, 1, nodes, relationships, seen_ids)

    return nodes, relationships

def process_replies(replies, parent_id, current_level, nodes, relationships, seen_ids):
    """Recursively process reply tweets"""
    for reply in replies:
        if not reply.get('content') and not reply.get('replies'):
            continue

        reply_id = reply.get('url', '')
        if reply_id:
            reply_id = reply_id.split('/')[-1].strip().lstrip("'")
        else:
            reply_id = f"no_url_{reply['timestamp']}_{reply['username']}"

        if reply_id in seen_ids:
            continue

        seen_ids.add(reply_id)
        nodes.append({
            'tweet_id': reply_id,
            'username': reply['username'],
            'timestamp': reply['timestamp'],
            'date': reply['date'],
            'content': reply['content'],
            'url': reply.get('url', ''),
            'level': current_level
        })

        relationships.append({
            'start_id': reply_id,
            'end_id': parent_id,
            'level': current_level,
            'type': 'reply_to'
        })

        if reply.get('replies'):
            process_replies(reply['replies'], reply_id, current_level + 1, nodes, relationships, seen_ids)

def save_to_csv(nodes, relationships, prefix='twitter_data'):
    """Save data to CSV files with IDs as plain strings (no quotes)"""
    # Nodes file
    nodes_header = ['tweet_id', 'username', 'timestamp', 'date', 'content', 'url', 'level']
    with open(f'{prefix}_nodes.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(nodes_header)

        # Write virtual ROOT node
        writer.writerow(['ROOT', 'root_system', '', '', 'Virtual root node', '', '-1'])

        for node in nodes:
            tweet_id = str(node['tweet_id'])
            content = node['content'].replace('\n', ' ').replace('\r', ' ').replace('"', "'").strip()
            writer.writerow([
                tweet_id,
                node['username'],
                node['timestamp'],
                node['date'],
                content,
                node['url'],
                str(node['level'])
            ])

    # Relationships file
    rels_header = ['start_id', 'end_id', 'level', 'type']
    with open(f'{prefix}_relationships.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(rels_header)

        for rel in relationships:
            start_id = str(rel['start_id'])
            end_id = str(rel['end_id']) if rel['end_id'] else ''
            writer.writerow([
                start_id,
                end_id,
                str(rel['level']),
                rel['type'].lower()
            ])

def analyze_data(nodes, relationships):
    """Print basic data statistics"""
    print("\n📊 数据统计：")
    print(f"- 节点数: {len(nodes)}")
    print(f"- 关系数: {len(relationships)}")

    level_counts = defaultdict(int)
    for rel in relationships:
        level_counts[rel['level']] += 1

    print("\n🔁 按层级分布的关系：")
    for level in sorted(level_counts.keys()):
        print(f"- Level {level}: {level_counts[level]} 条")


def run_processing(input_file, output_prefix):
    print("🚀 正在处理推文数据...")
    nodes, relationships = process_tweets(input_file)
    analyze_data(nodes, relationships)
    save_to_csv(nodes, relationships, prefix=output_prefix)
    print(f"\n✅ 数据处理完成！")
    return f"{output_prefix}_nodes.csv", f"{output_prefix}_relationships.csv"

def main():
    input_file = 'tweets_dog_2025-05-01_2025-06-01.json'  # 修改成你的文件名
    output_prefix = 'twitter_dog_data'

    print("🚀 正在处理推文数据...")
    nodes, relationships = process_tweets(input_file)

    analyze_data(nodes, relationships)

    print("\n💾 正在保存 CSV 文件...")
    save_to_csv(nodes, relationships, output_prefix)

    print(f"\n✅ 处理完成！生成文件：")
    print(f"- 节点文件: {output_prefix}_nodes.csv")
    print(f"- 关系文件: {output_prefix}_relationships.csv")

if __name__ == '__main__':
    main()
