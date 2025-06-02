import json
import csv
from datetime import datetime
from collections import defaultdict

def process_tweets(input_file):
    """处理推文数据，提取节点和关系"""
    with open(input_file, 'r', encoding='utf-8') as f:
        tweets = json.load(f)
    
    nodes = []
    relationships = []
    seen_ids = set()  # 用于跟踪已经处理过的tweet id
    
    for tweet in tweets:
        main_tweet_id = tweet['url'].split('/')[-1]
        
        # 检查主推文是否已经处理过
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
        
        relationships.append({
            'start_id': main_tweet_id,
            'end_id': '',
            'level': 0,
            'type': 'ORIGINAL'
        })
        
        process_replies(tweet['replies'], main_tweet_id, 1, nodes, relationships, seen_ids)
    
    return nodes, relationships

def process_replies(replies, parent_id, current_level, nodes, relationships, seen_ids):
    """递归处理回复推文"""
    for reply in replies:
        if not reply['content'] and not reply['replies']:
            continue
            
        reply_id = reply['url'].split('/')[-1] if reply['url'] else f"no_url_{reply['timestamp']}_{reply['username']}"
        
        # 检查回复是否已经处理过
        if reply_id in seen_ids:
            continue
            
        seen_ids.add(reply_id)
        nodes.append({
            'tweet_id': reply_id,
            'username': reply['username'],
            'timestamp': reply['timestamp'],
            'date': reply['date'],
            'content': reply['content'],
            'url': reply['url'],
            'level': current_level
        })
        
        relationships.append({
            'start_id': reply_id,
            'end_id': parent_id,
            'level': current_level,
            'type': 'REPLY_TO'
        })
        
        if reply['replies']:
            process_replies(reply['replies'], reply_id, current_level + 1, nodes, relationships, seen_ids)

def save_to_csv(nodes, relationships, prefix='twitter_data'):
    """将数据保存为CSV文件，确保ID完整显示"""
    # 节点文件
    nodes_header = ['tweet_id:ID', 'username', 'timestamp', 'date', 'content', 'url', 'level:int', ':LABEL']
    with open(f'{prefix}_nodes.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(nodes_header)
        for node in nodes:
            tweet_id = f"'{node['tweet_id']}" if str(node['tweet_id']).isdigit() else node['tweet_id']
            writer.writerow([
                tweet_id,
                node['username'],
                node['timestamp'],
                node['date'],
                node['content'].replace('\n', ' ').replace('\r', ' '),
                node['url'],
                node['level'],
                'Tweet'
            ])
    
    # 关系文件
    rels_header = [':START_ID', ':END_ID', 'level:int', ':TYPE']
    with open(f'{prefix}_relationships.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(rels_header)
        for rel in relationships:
            start_id = f"'{rel['start_id']}" if str(rel['start_id']).isdigit() else rel['start_id']
            end_id = f"'{rel['end_id']}" if rel['end_id'] and str(rel['end_id']).isdigit() else rel['end_id']
            writer.writerow([
                start_id,
                end_id,
                rel['level'],
                rel['type']
            ])

def analyze_data(nodes, relationships):
    """分析数据统计信息"""
    print("\n数据统计:")
    print(f"总节点数: {len(nodes)}")
    print(f"总关系数: {len(relationships)}")
    
    level_counts = defaultdict(int)
    for rel in relationships:
        level_counts[rel['level']] += 1
    
    print("\n各层级关系分布:")
    for level in sorted(level_counts.keys()):
        print(f"层级 {level}: {level_counts[level]} 条关系")

def main():
    input_file = 'tweets_dog_2025-05-01_2025-06-01.json'
    output_prefix = 'twitter_dog_data'
    
    print("开始处理推文数据...")
    nodes, relationships = process_tweets(input_file)
    
    analyze_data(nodes, relationships)
    
    print("\n保存CSV文件...")
    save_to_csv(nodes, relationships, output_prefix)
    
    print(f"\n处理完成！CSV文件已保存为:")
    print(f"- 节点文件: {output_prefix}_nodes.csv")
    print(f"- 关系文件: {output_prefix}_relationships.csv")

if __name__ == '__main__':
    main()