# wargame
import sys
from enum import Enum
from collections import deque
import copy
import cProfile
import re
import time

bestMove = None
BOARD_SIZE = 5
NODES_SEARCHED = 0
PRUNED_BRANCHES = 0

# Pretty printing
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Possible neighbors as tuples
UP = (-1,0)
DOWN = (1,0)
LEFT = (0,-1)
RIGHT = (0,1)
POTENTIAL_NEIGHBORS = (UP, DOWN, LEFT, RIGHT)
#-------------------#

class PlayerType(Enum):
    MaxPlayer = 1
    MinPlayer = 2

class Player(object):
    def __init__(self,ptype,name,isPruner=False):
        self.type = ptype
        self.name = name
        self.isPruner = isPruner
        self.prunedBranches = 0

        if self.isPruner:
            self.maxDepth = 4
        else:
            self.maxDepth = 2
        
        self.score = 0
        self.claimedCells = set()
        self.expandedNodeCount = 0
        self.moveCount = 0
        self.thinkTime = 0
        self.moveSequence = deque()

    def AddCell(self,cell):
        self.claimedCells.add(cell)
        self.score += int(cell.value)

    def RemoveCell(self,cell):
        self.claimedCells.remove(cell)
        self.score -= int(cell.value)

class MoveType(Enum):
    ParaDrop = 1
    Blitz = 2

class Game(object):
    def __init__(self,theBoard, thePlayers):
        self.theBoard = theBoard
        self.cells = set()
        self.GenerateCells()
        self.availableCells = set()
        self.takenCells = set()
        self.PopulateInitialCellState()
        self.currentPlayer = thePlayers[0]
        self.players = thePlayers
        self.depth = 0
        self.maxDepth = self.currentPlayer.maxDepth
        self.shouldPrune = False
        self.alpha = -sys.maxsize
        self.beta = sys.maxsize
        self.gameMoveSequence = deque()
        self.expandedNodeCount = 0

    def GenerateCells(self):
        for i in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                self.cells.add(BoardCell((i,x),self.theBoard[i][x]))

    def GetBoardCellByIndex(self,idx):
        for cell in self.cells:
            if cell.index == idx:
                return cell
        print "Invalid Cell: {}".format(idx)
        return None

    def PopulateInitialCellState(self):
        for cell in self.cells:
            self.availableCells.add(cell)

    def GetAvailableCells(self):
        return self.availableCells

    def SwapCurrentPlayer(self):
        if self.currentPlayer == self.players[0]:
            self.currentPlayer = self.players[1]
        else:
            self.currentPlayer = self.players[0]

    def setCurrentPlayerAsActive(self):
        self.currentPlayer.type = PlayerType.MaxPlayer
        if self.currentPlayer == self.players[0]:
            self.players[1].type = PlayerType.MinPlayer
        else:
            self.players[0].type = PlayerType.MinPlayer

    def GetDepth(self):
        return self.depth

    def setDepth(self,depth):
        self.depth = depth

    def Over(self):
        return (len(self.availableCells) == 0)

    def Heuristic(self):
        if self.currentPlayer.type == PlayerType.MaxPlayer:
            return self.currentPlayer.score - self.GetOpponent().score

        # Assuming we are playing against an optimal opponent.
        # -- At best, our current move will be equal to our opponent's previous move.
        # -- For every move in the current branch move history, compute the score.
        # -- If my score is less than 0 (i.e., suboptimal for this branch), return -sys.maxsize
        # -- Else, return the current score of this branch of moves.
        movesDq = copy.deepcopy(self.gameMoveSequence)
        mov = movesDq.pop()

        retVal = int(mov.value)  #int(movesDq.pop().value)
        for i in range(self.maxDepth-1):
            if (i % 2) != 0: # Our moves
                retVal += int(movesDq.pop().value)
            else: # Their moves
                retVal -= int(movesDq.pop().value)

        return retVal

    def MakeMove(self, move):
        if move.type == MoveType.ParaDrop:
            move.value = self.ParaDrop(move.cell)
        else:
            move.value = self.Blitz(move.cell)
        self.currentPlayer.moveCount += 1
        self.currentPlayer.moveSequence.append(move)
        self.gameMoveSequence.append(move)

    def ParaDrop(self, cell):
        if cell in self.availableCells:
            self.ClaimCell(cell)
            return cell.value
        print '!! Invalid ParaDrop {}'.format(cell.index)

    def Blitz(self,cell):
        moveScore = 0

        if cell in self.availableCells:
            self.ClaimCell(cell)
            moveScore += int(cell.value)

        opp = self.GetOpponent()
        for n in cell.neighbors:
            if n in opp.claimedCells:
                opp.RemoveCell(n)
                self.ClaimCell(n)
                moveScore += int(n.value)

        return moveScore

    def ClaimCell(self,cell):
        self.availableCells.discard(cell)
        self.takenCells.add(cell)
        self.currentPlayer.AddCell(cell)

    def AvailableMoves(self):
        moveset = deque()
        for cell in self.availableCells:
            moveset.append(Move(MoveType.ParaDrop,cell))
        for cell in self.currentPlayer.claimedCells:
            for n in cell.neighbors:
                if n in self.availableCells:
                    moveset.append(Move(MoveType.Blitz, self.GetBoardCellByIndex(n.index)))
        return moveset

    def PrintCurrentState(self):
        print '      A      B      C      D      E'#      F'#     G     H'
        for i in range(BOARD_SIZE):
            sys.stdout.write(str(i+1))
            for x in range(BOARD_SIZE):
                if BoardCell((i,x),self.theBoard[i][x], False) in self.players[1].claimedCells:
                    sys.stdout.write(' | ' + bcolors.OKGREEN + '{'+self.theBoard[i][x]+'}' + bcolors.ENDC)
                elif BoardCell((i,x),self.theBoard[i][x], False) in self.players[0].claimedCells:
                    sys.stdout.write(' | ' + bcolors.OKBLUE + '{'+self.theBoard[i][x]+'}' + bcolors.ENDC)
                else:
                    sys.stdout.write(' | {'+self.theBoard[i][x]+'}')
            print '\n' + '-'*60

    def PrintScores(self):
        print '---| Player 1:  Score - {}, {} Moves, Expanded Nodes - {}, Pruned Branches - {}'.format(self.players[0].score, self.players[0].moveCount, self.players[0].expandedNodeCount,self.players[0].prunedBranches)
        print '---| Player 2:  Score - {}, {} Moves, Expanded Nodes - {}, Pruned Branches - {}'.format(self.players[1].score, self.players[1].moveCount, self.players[1].expandedNodeCount,self.players[1].prunedBranches)
        print '---| Winner --> {}'.format(self.GetWinnerText())

    def GetOpponent(self):
        if self.currentPlayer == self.players[0]: return self.players[1]
        else: return self.players[0]

    def GetWinnerText(self):
        if int(self.players[0].score) > int(self.players[1].score): return 'Player 1'
        elif self.players[1].score > self.players[0].score: return 'Player 2'
        else: return 'Tie!'

    def GetPlayerText(self,p):
        if self.players[0] == p: return 'Player 1'
        else: return 'Player 2'

class Move(object):
    def __init__(self,mtype,cell):
        self.type = mtype
        self.cell = cell
        self.value = 0

class BoardCell(object):
    def __init__(self, index, value,gen=True):
        self.index = index
        self.value = value
        self.neighbors = []
        if gen: self.LocateNeighbors()

    def __hash__(self):
        return hash(self.index)

    def __eq__(self,other):
        if self.index == other.index: return True
        else: return False

    def LocateNeighbors(self):
        print '\nWorking on: {}:{}'.format(self.index,self.value)
        for n in POTENTIAL_NEIGHBORS:
            if ((0 <= self.index[0]+n[0] < BOARD_SIZE) and \
                (0 <= self.index[1]+n[1] < BOARD_SIZE)):
                cellVal = theBoard[self.index[0]+n[0]][self.index[1]+n[1]]
                tempCell = BoardCell((self.index[0]+n[0],self.index[1]+n[1]), cellVal, False)
                print "Adding neighbor: " + cellVal
                self.neighbors.append(tempCell)

def MiniMax(curGameState):
    if curGameState.GetDepth() == curGameState.maxDepth:
        #print "Max Depth Reached"
        return curGameState.Heuristic()

    global NODES_SEARCHED
    NODES_SEARCHED += 1

    if curGameState.Over():
        return curGameState.currentPlayer.score

    if curGameState.currentPlayer.type == PlayerType.MaxPlayer:
        alpha = -sys.maxsize
    else:
        alpha = sys.maxsize

    moveset = curGameState.AvailableMoves()
    for move in moveset:
        deltaGameState = copy.deepcopy(curGameState)
        deltaGameState.MakeMove(move)
        deltaGameState.setDepth(deltaGameState.GetDepth() + 1)
        deltaGameState.SwapCurrentPlayer()

        subalpha = MiniMax(deltaGameState)

        if curGameState.currentPlayer.type == PlayerType.MaxPlayer:
            if curGameState.GetDepth() == 0 and alpha < subalpha:
                global bestMove 
                bestMove = move
                #print '[{}] {} ---> {} ... alpha: {}, subalpha: {}'.format(bestMove.type, bestMove.cell.index, bestMove.value, alpha, subalpha)
            alpha = max(alpha,subalpha)
            curGameState.alpha = alpha
        else:
            alpha = min(alpha,subalpha)
            curGameState.beta = alpha
        
        if curGameState.shouldPrune and \
           curGameState.GetDepth() != 0 and \
           curGameState.beta <= curGameState.alpha:
            global PRUNED_BRANCHES
            PRUNED_BRANCHES += 1
            break

    return alpha

def AIGuess(game):
    game.setCurrentPlayerAsActive()
    start = time.time()
    MiniMax(game)
    end = time.time()
    game.currentPlayer.thinkTime += round(end-start,4)
    return bestMove

#clunky
def HumanGuess(game):
    game.setCurrentPlayerAsActive()
    validMove = False
    while not validMove:
        print '+'*55
        nextMoveType = raw_input('Choose a move type --- Para-drop {1}  |  Death-blitz {2}:  ')
        try:
            MoveType(int(nextMoveType))
        except:
            print 'Invalid Move Type chosen. Please try again.'
            continue

        nextMoveCell = raw_input('Choose a cell (e.g., B4):   ')
        try:
            int(nextMoveCell[1])
        except:
            print '{} is an invalid index.'.format(nextMoveCell[1])
            continue

        yVal = ord(nextMoveCell[0].upper()) - 65
        xVal = int(nextMoveCell[1]) - 1
        cell = game.GetBoardCellByIndex((xVal,yVal))
        if cell in game.takenCells:
            print 'That cell is already claimed. Please try again.'
            continue
        elif MoveType(int(nextMoveType)) == MoveType.Blitz:
            for c in cell.neighbors:
                if c in game.currentPlayer.claimedCells:
                    validMove = True
                    break
            if not validMove:
                print 'That is not a valid Blitz.'
        else:
            validMove = True

    nextMove = Move(MoveType(int(nextMoveType)),cell)
    return nextMove

def Run(game):
    while(game.GetAvailableCells()):
        print '\n' + '='*70
        print '\n\tCurrent Player: {}, maxDepth: {}\t ... thinking'.format(game.GetPlayerText(game.currentPlayer), game.currentPlayer.maxDepth)
        
        game.shouldPrune = game.currentPlayer.isPruner

        if game.currentPlayer == player1:
            nextMove = HumanGuess(game)
            #nextMove = AIGuess(game)
        else:
            #nextMove = HumanGuess(game)
            nextMove = AIGuess(game)

        game.MakeMove(nextMove)
        game.currentPlayer.prunedBranches += PRUNED_BRANCHES
        global PRUNED_BRANCHES
        PRUNED_BRANCHES = 0
        print "---===| Player: {} --->  {}  --->  {}  --->  {} Points.".format(game.GetPlayerText(game.currentPlayer), nextMove.type, nextMove.cell.index, nextMove.value )
        print "---===| Avg ThinkTime: {} --- Branches Pruned So Far: {}".format(game.currentPlayer.thinkTime/game.currentPlayer.moveCount, game.currentPlayer.prunedBranches)
        game.currentPlayer.expandedNodeCount += NODES_SEARCHED
        global NODES_SEARCHED
        NODES_SEARCHED = 0

        game.PrintCurrentState()
        game.SwapCurrentPlayer()
        game.maxDepth = game.currentPlayer.maxDepth

##############################################################
#                     Begin __main__                         #
##############################################################
if __name__ == '__main__':
    theBoard = [[0 for x in range(BOARD_SIZE)] for x in range(BOARD_SIZE)] 

    with open("game.txt", "r") as f:
        row = 0
        for line in f:
            col = 0
            for val in line.split():
                theBoard[row][col] = val
                col += 1
            row += 1

    player1 = Player(PlayerType.MaxPlayer, 'Player 1', False)
    player2 = Player(PlayerType.MinPlayer, 'Player 2', False)
    GameState = Game(theBoard, (player1,player2))
    GameState.PrintCurrentState()
    #cProfile.run('Run(GameState)')
    Run(GameState)
    GameState.PrintCurrentState()
    GameState.PrintScores()